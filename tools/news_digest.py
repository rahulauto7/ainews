"""
One compact, curation-ready view of today's scrape: .tmp/digest.md

rss_articles.json is ~400 KB (~100k tokens), and runs before 2026-09-15 read it
through ad-hoc dumps, then grepped the last three editions keyword by keyword
to spot repeats and re-read yesterday's builder for carry-forward decisions.
This prints all of that once, in roughly a tenth of the size:

  - every article as one line: [idx] date source | headline, grouped by feed
    category, biggest story (most outlets) first; a short text snippet only
    for feeds that carry real article text (proxy items carry just the headline)
  - PRINTED mm-dd when the story already ran in one of the last three editions
  - only opportunity items that pass the gate (is_opportunity)
  - yesterday's opportunities, open-model table and rejections, so nothing
    needs to be re-derived from backups or old builder scripts

Usage:
  python3 tools/news_digest.py            # writes .tmp/digest.md, prints its size
  Then Read .tmp/digest.md (in two halves if the Read tool truncates it).
"""

import html
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import web_text
from builder_helpers import OPPORTUNITY_KEYS, prior_editions
from scrape_rss_feeds import _same_story, title_tokens

OUT_FILE = os.path.join(web_text.TMP_DIR, "digest.md")
TITLE_MAX = 120
SNIPPET_MAX = 140

# Order follows the PDF's sections, so the digest reads top to bottom in the
# order the builder is written.
CATEGORY_ORDER = [
    ("opportunity", "Opportunity feeds -> AI Hackathons / Grants, Fellowships & Programs"),
    ("quantum", "Quantum (Thursdays)"),
    ("elon_xai", "Musk / xAI"),
    ("indian", "Indian publishers"),
    ("anthropic_claude", "Anthropic & Claude (Google News proxies)"),
    ("open_model", "Open models"),
    ("general", "General AI news"),
    ("company_blog", "Company blogs"),
    ("showcase", "Product Hunt"),
    ("ai_research", "arXiv (titles only)"),
]

SHORT_SOURCE = {
    "Anthropic News (via Google News)": "GN-Anthropic",
    "Claude Code (via Google News)": "GN-ClaudeCode",
    "Elon Musk on X (via Google News)": "GN-Musk",
    "Open Models (via Google News)": "GN-OpenModels",
    "Open Model Benchmarks (via Google News)": "GN-Benchmarks",
    "AI Hackathons (via Google News)": "GN-Hackathons",
    "AI Competitions (via Google News)": "GN-Competitions",
    "AI Programs (via Google News)": "GN-Programs",
    "AI Applications Open (via Google News)": "GN-Applications",
    "Quantum + AI (via Google News)": "GN-Quantum",
}


def _plain(text):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    # Reuters copy (via Economic Times) is peppered with zero-width characters.
    text = re.sub("[\u200b-\u200d\u2060\ufeff]", "", text)
    return " ".join(text.split())


def snippet(article):
    """Text beyond the headline, or '' for proxy items that carry only the headline."""
    if "Google News" in article["source"] or article["source"].startswith("arXiv"):
        return ""
    s = _plain(article.get("summary"))
    head = article["title"][:40]
    if not s or s.startswith(head) or len(s) < len(article["title"]) + 30:
        return ""
    return s[:SNIPPET_MAX] + ("..." if len(s) > SNIPPET_MAX else "")


def printed_index(editions):
    """[(tokens, url, date)] for every story in the prior editions."""
    out = []
    for date, edition in editions:
        for stories in edition.get("sections", {}).values():
            for s in stories:
                out.append((title_tokens(s.get("title", "")), s.get("url"), date[5:]))
    return out


def printed_on(article, index, decoded):
    tokens = title_tokens(article["title"])
    url = decoded.get(article["url"], article["url"])
    dates = sorted({d for t, u, d in index if u in (article["url"], url) or _same_story(tokens, t)})
    return ",".join(dates)


def build():
    data, arts = web_text.load_articles()
    scrape_day = web_text.local_date(data["scraped_at"])
    editions = prior_editions(scrape_day)
    index = printed_index(editions)
    decoded = web_text.load_decoded_cache()

    lines = []
    w = lines.append
    weekday = datetime.strptime(scrape_day, "%Y-%m-%d").strftime("%A")
    w(f"# Digest for {scrape_day} ({weekday}) - {len(arts)} articles, scraped {data['scraped_at'][:16]} UTC")
    w(f"Quantum + AI: {'INCLUDED today' if data.get('quantum_day') else 'skipped (not Thursday)'}. "
      f"Prior editions compared: {', '.join(d for d, _ in editions) or 'none found'}.")
    w("Line format: [idx] mm-dd source | headline  xN = outlets carrying it  PRINTED = ran in that edition")
    w("Read real text: python3 tools/fetch_articles.py IDX IDX ...")

    if editions:
        date, last = editions[0]
        w(f"\n## Yesterday's opportunities ({date}) - carry-forward candidates; `find_opportunities.py recheck` verifies all")
        for key in OPPORTUNITY_KEYS:
            for s in last.get("sections", {}).get(key, []):
                runs = [d[5:] for d, e in editions
                        if any(x.get("url") == s.get("url") for x in e.get("sections", {}).get(key, []))]
                w(f"- [{'hack' if key == 'ai_hackathons' else 'prog'}] {s['title'][:90]} | "
                  f"deadline: {s.get('deadline', '-')} | printed {','.join(sorted(runs))}")
        rejected = [r for _, e in editions for r in (e.get("curation_log") or {}).get("rejected", [])]
        if rejected:
            w("\n## Rejected in recent runs - do not re-investigate unless the reason may have changed")
            for r in rejected:
                w(f"- {r['name']} ({r['date'][5:]}): {r['reason']}")
        block = (last.get("section_extras") or {}).get("open_model_landscape")
        if block:
            rows = "; ".join(f"{r['use_case']} = {r['model']} ({r['licence'][:30]})" for r in block["best_for"])
            w(f"\n## Open-model table, as_of {block.get('as_of')}: {rows}")
            w("carry_forward_best_for() in builder_helpers reuses it; change a row only on new evidence.")

    by_cat = {}
    for i, a in enumerate(arts):
        by_cat.setdefault(a.get("category", "general"), []).append((i, a))
    seen_cats = {c for c, _ in CATEGORY_ORDER}
    order = CATEGORY_ORDER + [(c, c) for c in by_cat if c not in seen_cats]

    for cat, label in order:
        items = by_cat.get(cat, [])
        if cat == "opportunity":
            gated = [(i, a) for i, a in items if a.get("is_opportunity")]
            label += f" - {len(gated)} pass the gate, {len(items) - len(gated)} rejected and not shown"
            items = gated
        if not items:
            continue
        # Most outlets first; newest first among equals (two stable sorts).
        items.sort(key=lambda ia: ia[1].get("published") or "", reverse=True)
        items.sort(key=lambda ia: -(ia[1].get("duplicate_count") or 1))
        w(f"\n## {label} ({len(items)})")
        for i, a in items:
            src = SHORT_SOURCE.get(a["source"], a["source"][:16])
            title = a["title"] if len(a["title"]) <= TITLE_MAX else a["title"][:TITLE_MAX - 3] + "..."
            extra = ""
            if (a.get("duplicate_count") or 1) > 1:
                extra += f"  x{a['duplicate_count']}"
            if not a["source"].startswith("arXiv"):
                seen = printed_on(a, index, decoded)
                if seen:
                    extra += f"  PRINTED {seen}"
            w(f"[{i}] {a.get('published_date', '')[5:]} {src} | {title}{extra}")
            snip = snippet(a)
            if snip:
                w(f"    > {snip}")

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    text = "\n".join(lines)
    print(f"Wrote {OUT_FILE}: {len(lines)} lines, {len(text):,} chars (~{len(text) // 4:,} tokens)")


if __name__ == "__main__":
    build()
