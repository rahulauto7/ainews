"""
One compact, curation-ready view of today's scrape: .tmp/digest.md

rss_articles.json is ~400 KB (~100k tokens), and runs before 2026-09-15 read it
through ad-hoc dumps, then grepped the last three editions keyword by keyword
to spot repeats and re-read yesterday's builder for carry-forward decisions.
This prints all of that once, in roughly a tenth of the size:

  - every article as one line: [idx] date source | headline, grouped by feed
    category in the PDF's section order, biggest story (most outlets) first,
    direct feeds before search proxies; a short text snippet only for feeds that
    carry real article text (proxy items carry just the headline)
  - each group capped (cap_for) so the digest stays readable with 200+ sources;
    the rest are counted on one line and stay in rss_articles.json
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

# Order follows the PDF's sixteen sections, so the digest reads top to bottom in
# the order the builder is written. Each label names, after "->", the section the
# group feeds: this list is also the category-to-section map.
CATEGORY_ORDER = [
    ("opportunity", "Opportunity feeds -> AI Hackathons / AI Grants, Fellowships & Programs"),
    ("rsi", "Self-improvement, safety, alignment -> AI Self-Improvement (RSI)"),
    ("ai_research", "Research: arXiv titles, lab and university feeds -> AI Self-Improvement (RSI)"),
    ("quantum", "Quantum, Thursdays -> Quantum + AI"),
    ("problems", "AI failures and gaps -> Unaddressed AI Problems"),
    ("automation", "Automation, agents, enterprise AI -> AI Automation & Business"),
    ("business", "Funding, startups, markets -> AI Business Opportunities"),
    ("showcase", "Product Hunt -> AI Business Opportunities"),
    ("indian", "Indian publishers -> Indian AI Industry"),
    ("world", "Regional editions and outlets worldwide, policy and regulators -> Global AI News"),
    ("world_lang", "Non-English press (summarise in English, English title) -> Global AI News"),
    ("general", "General AI news -> Global AI News"),
    ("company_blog", "Other AI companies' own blogs -> Global AI News"),
    ("openai", "OpenAI -> OpenAI"),
    ("google", "Google, Gemini, DeepMind -> Google AI"),
    ("anthropic_claude", "Anthropic and Claude -> Anthropic & Claude Code"),
    ("xai_grok", "xAI and Grok -> xAI & Grok"),
    ("open_model", "Open models -> Open Models & Open Weights"),
    ("closed_model", "Closed models -> Closed Models & Frontier APIs"),
    ("elon_musk", "Elon Musk in his own words -> Elon Musk on AI"),
    ("video", "YouTube and podcasts: leads for any section"),
    ("social", "X posts, Hacker News, Lobsters: leads for any section"),
    ("forums", "Reddit and Bluesky: leads for any section"),
]

# How many articles each group shows, so the digest stays near its old size (about
# 17k tokens with 34 feeds; keep it under 35k). This limits what the curator reads,
# never how many stories a section prints: the rest stay in rss_articles.json.
DIGEST_CAP = 40
_CAPS = {"general": 60, "world": 50, "world_lang": 30, "ai_research": 25, "video": 30,
         "social": 25, "forums": 25}
SHORT_MAX = 22


def cap_for(category):
    return _CAPS.get(category, DIGEST_CAP)


def _is_proxy(source):
    return "via Google News" in source or "via Bing News" in source


def ranked(items):
    """[(idx, article)] best first: most outlets, then direct feeds before search
    proxies, then newest."""
    items = sorted(items, key=lambda ia: ia[1].get("published") or "", reverse=True)
    return sorted(items, key=lambda ia: (-(ia[1].get("duplicate_count") or 1),
                                         _is_proxy(ia[1].get("source", ""))))


def short_source(name):
    """A source name short enough for a digest line."""
    m = re.match(r"(.+?) (all posts )?on X \(via Google News\)$", name)
    if m:
        short = "X-" + m.group(1)
    elif name.endswith(" (via Google News)"):
        short = "GN-" + name[: -len(" (via Google News)")]
    elif name.endswith(" (via Bing News)"):
        short = "Bing-" + name[: -len(" (via Bing News)")]
    elif "YouTube" in name:
        short = "YT-" + re.sub(r"\s*\(?YouTube\)?\s*", " ", name).strip()
    elif name.endswith(" on Bluesky"):
        short = "Bsky-" + name[: -len(" on Bluesky")]
    elif name.endswith(" podcast"):
        short = "Pod-" + name[: -len(" podcast")]
    else:
        short = name[:16]
    return short[:SHORT_MAX]


def _plain(text):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    # Reuters copy (via Economic Times) is peppered with zero-width characters.
    text = re.sub("[\u200b-\u200d\u2060\ufeff]", "", text)
    return " ".join(text.split())


def snippet(article):
    """Text beyond the headline, or '' for proxy items that carry only the headline."""
    if _is_proxy(article["source"]) or article["source"].startswith("arXiv"):
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
        items = ranked(items)
        cap = cap_for(cat)
        hidden = len(items) - cap
        w(f"\n## {label} ({len(items)})")
        for i, a in items[:cap]:
            src = short_source(a["source"])
            title = a["title"] if len(a["title"]) <= TITLE_MAX else a["title"][:TITLE_MAX - 3] + "..."
            extra = ""
            if (a.get("duplicate_count") or 1) > 1:
                extra += f"  x{a['duplicate_count']}"
            if not a["source"].startswith("arXiv"):
                seen = printed_on(a, index, decoded)
                if seen:
                    extra += f"  PRINTED {seen}"
            if a.get("also_in"):
                extra += f"  {{also: {', '.join(a['also_in'])}}}"
            w(f"[{i}] {a.get('published_date', '')[5:]} {src} | {title}{extra}")
            snip = snippet(a)
            if snip:
                w(f"    > {snip}")
        if hidden > 0:
            w(f"(+{hidden} more in rss_articles.json, not shown)")

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    text = "\n".join(lines)
    print(f"Wrote {OUT_FILE}: {len(lines)} lines, {len(text):,} chars (~{len(text) // 4:,} tokens)")


if __name__ == "__main__":
    build()
