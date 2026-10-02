"""Cases for the source registry (tools/feed_sources.py) and the scraper around it.

The registry replaced the hand-written FEEDS literal on 2026-10-02: the 32 feeds
kept from it plus 182 sources tested that day, each tagged with the digest group
it feeds. Rules it must keep:

  - keyless: nothing that needs an API key, even when the key sits in .env
  - every PDF section has at least one source feeding it
  - the lookback windows follow the category: quantum 7 days, opportunities 30,
    everything else the 24-hour news rule

Run: python3 tools/tests/test_sources.py
"""

import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import feed_sources
import scrape_rss_feeds
from generate_pdf import SECTION_ORDER

# The category-to-section map of plan-2.md Task 5. "video" and "social" are leads
# for any section, so they feed none on their own.
SECTIONS_FED_BY = {
    "opportunity": ["ai_hackathons", "product_showcase_opportunities"],
    "rsi": ["ai_self_improvement_rsi"],
    "ai_research": ["ai_self_improvement_rsi"],
    "quantum": ["quantum_ai_research"],
    "problems": ["unaddressed_ai_problems"],
    "automation": ["ai_business_automation"],
    "business": ["ai_business_opportunities"],
    "showcase": ["ai_business_opportunities"],
    "indian": ["indian_ai_industry"],
    "world": ["global_ai_news"],
    "general": ["global_ai_news"],
    "company_blog": ["global_ai_news"],
    "openai": ["openai_news"],
    "google": ["google_ai_news"],
    "anthropic_claude": ["anthropic_claude_news"],
    "xai_grok": ["xai_grok_news"],
    "open_model": ["open_model_landscape"],
    "closed_model": ["closed_model_landscape"],
    "elon_musk": ["elon_musk_ai_vision"],
    "video": [],
    "social": [],
}

KEYED_HOSTS = {"api.twitter.com", "api.x.com", "www.googleapis.com", "newsapi.org"}
KEYED_PARAMS = ("key=", "apikey", "api_key", "token=")


def check(failures, cond, msg):
    if not cond:
        failures.append(msg)


def main():
    failures, cases = [], 0
    rss, extra = feed_sources.RSS, feed_sources.EXTRA

    # ── 1. Names unique, URLs https ──────────────────────────────────────────
    names = [r[0] for r in rss] + [e[0] for e in extra]
    cases += 2
    check(failures, len(names) == len(set(names)),
          f"duplicate source names: {sorted({n for n in names if names.count(n) > 1})}")
    bad = [name for name, url, _c, _f in rss if not url.startswith("https://")]
    check(failures, not bad, f"not https: {bad}")

    # ── 2. Keyless ───────────────────────────────────────────────────────────
    keyed = [name for name, url, _c, _f in rss
             if any(p in url.lower() for p in KEYED_PARAMS)
             or urllib.parse.urlparse(url).netloc in KEYED_HOSTS]
    cases += 1
    check(failures, not keyed, f"sources that need an API key: {keyed}")

    # ── 3. Every section is fed ──────────────────────────────────────────────
    categories = {r[2] for r in rss} | {e[1] for e in extra}
    cases += 1
    unknown = sorted(c for c in categories if c not in SECTIONS_FED_BY)
    check(failures, not unknown, f"categories with no section: {unknown}")
    fed = {s for c in categories for s in SECTIONS_FED_BY.get(c, [])}
    for key in SECTION_ORDER:
        cases += 1
        check(failures, key in fed, f"no source feeds section {key}")

    # ── 4. Windows follow the category ───────────────────────────────────────
    w = scrape_rss_feeds.window_hours_for
    cases += 3
    check(failures, w("AI Grants (via Google News)") == 720,
          f"opportunity window: {w('AI Grants (via Google News)')}")
    check(failures, w("The Quantum Insider") == 166,
          f"quantum window: {w('The Quantum Insider')}")
    check(failures, w("OpenAI (via Google News)") == 22 and
          "OpenAI (via Google News)" in scrape_rss_feeds.FEEDS,
          "OpenAI (via Google News) must be registered with the 22-hour news window")

    # ── 5. Dead feeds are gone ───────────────────────────────────────────────
    cases += 2
    check(failures, "ZDNet AI" not in scrape_rss_feeds.FEEDS, "ZDNet AI (404) is still scraped")
    check(failures, "xAI Blog" not in scrape_rss_feeds.FEEDS, "xAI Blog (404) is still scraped")

    # ── Flags reach the scraper's sets ───────────────────────────────────────
    cases += 3
    check(failures, "Inc42" in getattr(scrape_rss_feeds, "AI_FILTER_SOURCES", ()),
          "Inc42 carries the ai flag, so its non-AI stories must be filtered")
    check(failures, "Teslarati" in getattr(scrape_rss_feeds, "MUSK_FILTER_SOURCES", ()),
          "Teslarati carries the musk flag")
    check(failures, "OpenAI (via Bing News)" in getattr(scrape_rss_feeds, "BROWSER_UA_SOURCES", ()),
          "Bing News refuses the bot User-Agent")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
