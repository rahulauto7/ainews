"""
Read the real articles behind shortlisted feed items, in one call.

259 of the 402 articles scraped on 2026-09-15 were Google News proxy items whose
"summary" is only the headline, so every story needed a WebSearch or WebFetch
before it could be written - one model turn each. This tool decodes the proxy
links, fetches every publisher page in parallel, caches the text under
.tmp/articles/, and prints a capped excerpt per article.

Usage:
  python3 tools/fetch_articles.py 3 5 7 11 51          # indices into rss_articles.json
  python3 tools/fetch_articles.py 51 --chars 4000      # longer excerpt, served from cache
  python3 tools/fetch_articles.py 3 5 --chars 0        # status lines only
  python3 tools/fetch_articles.py --url URL --grep "deadline|prize"

Flags printed per article:
  OLD      the page's own publish date is more than 3 days before the scrape -
           a resurfaced story, not today's news (see Lessons 2026-09-11)
  THIN     under 400 characters of body text - paywall or client-rendered page
  FAILED   could not be fetched; confirm by one web search only if the story matters
  X POST   the post could not be read (decode or embed failure); the feed title
           is all there is. A post that IS read prints in full, quoted post
           and reply line included, with its own timestamp on the head line.
           Pass that timestamp to S(..., published_at=...) so the 24-hour rule
           measures the post, not the day Google indexed it.
"""

import argparse
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import web_text

CACHE_DIR = os.path.join(web_text.TMP_DIR, "articles")
OLD_AFTER_DAYS = 3
THIN_BELOW = 400
# Organiser pages change (a hackathon closes, a deadline moves), so a cached
# page is only trusted for the run that fetched it.
CACHE_MAX_AGE_HOURS = 12


def _cache_path(url):
    return os.path.join(CACHE_DIR, hashlib.sha1(url.encode()).hexdigest()[:16] + ".json")


def fetch_one(url, decoded_cache):
    """Fetch (or load from cache) one feed URL. Never raises."""
    path = _cache_path(url)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            rec = json.load(f)
        age = datetime.now() - datetime.fromisoformat(rec["fetched_at"])
        if age < timedelta(hours=CACHE_MAX_AGE_HOURS):
            return rec
    rec = {"feed_url": url, "url": url, "error": None}
    try:
        rec["url"] = web_text.decode_google_news(url, decoded_cache)
        if web_text.is_x_url(rec["url"]):
            # Read through the keyless embed endpoint. A failed read keeps the old
            # behaviour - the feed title stands in - and never aborts the batch.
            try:
                rec.update(web_text.tweet_record(web_text.fetch_tweet(rec["url"])))
                rec["x_post"] = True
            except Exception:
                rec["error"] = "X POST"
        else:
            html, final = web_text.fetch_html(rec["url"])
            rec.update(web_text.extract_article(html))
            rec["page"] = web_text.visible_text(html)[:80000]  # for --grep: sidebars hold deadlines
            rec["final_url"] = final
    except Exception as e:  # report, don't abort the batch
        rec["error"] = f"FAILED: {type(e).__name__}: {str(e)[:90]}"
    rec["fetched_at"] = datetime.now().isoformat(timespec="seconds")
    # Failures are not cached, so a re-run retries them. That includes a failed X
    # read: the embed endpoint answers 429 under load, and a cached failure would
    # keep the post's own timestamp from the 24h rule for the rest of the run.
    if not rec["error"]:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False)
    return rec


def flags_for(rec, scrape_date):
    flags = []
    if rec.get("error"):
        flags.append(rec["error"])
        return flags
    if rec.get("published") and scrape_date:
        pub = datetime.strptime(rec["published"], "%Y-%m-%d")
        if pub < scrape_date - timedelta(days=OLD_AFTER_DAYS):
            flags.append(f"OLD: page dated {rec['published']}")
    # A post is short by nature; THIN is for article pages that failed to render.
    if len(rec.get("text") or "") < THIN_BELOW and not rec.get("x_post"):
        flags.append("THIN")
    return flags


def render(label, rec, chars, scrape_date):
    domain = urlparse(rec.get("url") or "").netloc.replace("www.", "")
    flags = flags_for(rec, scrape_date)
    published = rec.get("published_at") if rec.get("x_post") else rec.get("published")
    head = f"[{label}] {domain} | published {published or '?'} | {len(rec.get('text') or ''):,} chars"
    if flags:
        head += " | " + " | ".join(flags)
    lines = [head]
    if chars and not rec.get("error"):
        if rec.get("description"):
            lines.append("  desc: " + rec["description"][:300])
        text = (rec.get("text") or "").replace("\n", " / ")
        lines.append("  " + text[:chars] + (" [...]" if len(text) > chars else ""))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("indices", nargs="*", type=int, help="indices into .tmp/rss_articles.json")
    ap.add_argument("--chars", type=int, default=1500, help="excerpt length per article (0 = status only)")
    ap.add_argument("--url", action="append", default=[], help="fetch an arbitrary page (repeatable)")
    ap.add_argument("--grep", help="with --url: print only snippets around this regex")
    args = ap.parse_args()
    if not args.indices and not args.url:
        ap.error("give article indices or --url")

    decoded = web_text.load_decoded_cache()
    jobs = []  # (label, url)
    scrape_date = None
    if args.indices:
        data, arts = web_text.load_articles()
        scrape_date = datetime.strptime(web_text.local_date(data["scraped_at"]), "%Y-%m-%d")
        for i in args.indices:
            if not 0 <= i < len(arts):
                print(f"[{i}] no such article (rss_articles.json has {len(arts)})")
                continue
            jobs.append((str(i), arts[i]["url"]))
    jobs += [(u, u) for u in args.url]

    # Google rate-limits bursts of decode requests, so decode with less concurrency.
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(lambda job: fetch_one(job[1], decoded), jobs))
    web_text.save_decoded_cache(decoded)

    for (label, _), rec in zip(jobs, results):
        if args.grep and label in args.url and not rec.get("error"):
            print(f"[{label}]")
            text = rec.get("page") or rec.get("text") or ""
            snippets = web_text.grep_context(text, args.grep, max_matches=8)
            print("\n".join("  " + s for s in snippets) or "  (no match)")
        else:
            print(render(label, rec, args.chars, scrape_date))

    failed = [label for (label, _), rec in zip(jobs, results) if (rec.get("error") or "").startswith("FAILED")]
    print(f"\n{len(jobs)} requested, {len(jobs) - len(failed)} ok" + (f", failed: {' '.join(failed)}" if failed else ""))


if __name__ == "__main__":
    main()
