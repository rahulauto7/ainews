"""
Read the real articles behind shortlisted feed items, in one call.

259 of the 402 articles scraped on 2026-09-15 were Google News proxy items whose
"summary" is only the headline, so every story needed a WebSearch or WebFetch
before it could be written - one model turn each. This tool decodes the proxy
links, fetches every publisher page in parallel, caches the text under
.tmp/articles/, and prints a capped excerpt per article.

Usage:
  python3 tools/fetch_articles.py 3 5 7 11 51          # indices into rss_articles.json
  python3 tools/fetch_articles.py 51 --chars 8000      # longer excerpt, served from cache
  python3 tools/fetch_articles.py 3 5 --chars 0        # status lines only
  python3 tools/fetch_articles.py 3 --no-fallback      # the story's own page only
  python3 tools/fetch_articles.py --url URL --grep "deadline|prize"

The excerpt defaults to 5,000 characters: enough of most articles to explain the
story in full, which is what every summary now does (rahul, 2026-10-03).

When a story's own page is blocked, paywalled or empty (FAILED / THIN), the
same story is read from another outlet instead: first the other outlets the
scrape found carrying it (`alternates` in rss_articles.json), then a keyless
Google News search of the headline. The head line then says `read via <outlet>`,
and that outlet's URL is printed so S(..., url=..., source=...) can point the
story at the page the reader can actually open.

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


def _usable(rec):
    """True for a fetched page with enough body text to write from."""
    return not rec.get("error") and (rec.get("x_post") or len(rec.get("text") or "") >= THIN_BELOW)


def _domain(url):
    return urlparse(url or "").netloc.lower().replace("www.", "")


def read_elsewhere(article, rec, decoded_cache, max_tries=4):
    """The same story from another outlet, when `rec` (its own page) is unusable.

    Tries the outlets the scrape found carrying it, then a Google News search of
    the headline. Returns the first usable record with `read_via` set, or None.
    Never raises: a failed fallback leaves the original flags in place.
    """
    own = {_domain(rec.get("url")), _domain(article.get("url"))}
    candidates = [(a["source"], a["url"]) for a in article.get("alternates") or []]
    tried = 0
    for searched in (False, True):
        if searched:
            try:
                hits = web_text.search_google_news(web_text.search_terms(article.get("title")))
            except Exception:  # noqa: BLE001 - the search is a bonus, never a failure
                return None
            candidates = [(h["source"], h["url"]) for h in hits[:8]]
        for source, url in candidates:
            if tried >= max_tries * 2:
                return None
            alt = fetch_one(url, decoded_cache)
            tried += 1
            if _domain(alt.get("url")) in own or not _usable(alt):
                continue
            alt = dict(alt)
            alt["read_via"] = source + (" (found by search)" if searched else "")
            return alt
    return None


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
    if rec.get("read_via"):
        head += f" | read via {rec['read_via']}: {rec.get('final_url') or rec.get('url')}"
    elif rec.get("own_page_problem"):
        head += f" | own page {rec['own_page_problem']}, no other outlet found"
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
    ap.add_argument("--chars", type=int, default=5000, help="excerpt length per article (0 = status only)")
    ap.add_argument("--no-fallback", action="store_true",
                    help="do not read a blocked or thin story from another outlet")
    ap.add_argument("--url", action="append", default=[], help="fetch an arbitrary page (repeatable)")
    ap.add_argument("--grep", help="with --url: print only snippets around this regex")
    args = ap.parse_args()
    if not args.indices and not args.url:
        ap.error("give article indices or --url")

    decoded = web_text.load_decoded_cache()
    jobs = []  # (label, url, article or None)
    scrape_date = None
    if args.indices:
        data, arts = web_text.load_articles()
        scrape_date = datetime.strptime(web_text.local_date(data["scraped_at"]), "%Y-%m-%d")
        for i in args.indices:
            if not 0 <= i < len(arts):
                print(f"[{i}] no such article (rss_articles.json has {len(arts)})")
                continue
            jobs.append((str(i), arts[i]["url"], arts[i]))
    jobs += [(u, u, None) for u in args.url]

    def run(job):
        _, url, article = job
        rec = fetch_one(url, decoded)
        if article is not None and not args.no_fallback and not _usable(rec) and not rec.get("x_post"):
            alt = read_elsewhere(article, rec, decoded)
            if alt:
                return alt
            rec = dict(rec, own_page_problem=(rec.get("error") or "THIN").split(":")[0])
        return rec

    # Google rate-limits bursts of decode requests, so decode with less concurrency.
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(run, jobs))
    web_text.save_decoded_cache(decoded)

    for (label, _, _), rec in zip(jobs, results):
        if args.grep and label in args.url and not rec.get("error"):
            print(f"[{label}]")
            text = rec.get("page") or rec.get("text") or ""
            snippets = web_text.grep_context(text, args.grep, max_matches=8)
            print("\n".join("  " + s for s in snippets) or "  (no match)")
        else:
            print(render(label, rec, args.chars, scrape_date))

    failed = [label for (label, _, _), rec in zip(jobs, results) if (rec.get("error") or "").startswith("FAILED")]
    elsewhere = [label for (label, _, _), rec in zip(jobs, results) if rec.get("read_via")]
    print(f"\n{len(jobs)} requested, {len(jobs) - len(failed)} ok"
          + (f", read elsewhere: {' '.join(elsewhere)}" if elsewhere else "")
          + (f", failed: {' '.join(failed)}" if failed else ""))


if __name__ == "__main__":
    main()
