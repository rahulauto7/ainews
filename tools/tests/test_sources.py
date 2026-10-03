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

import contextlib
import io
import json
import os
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import feedparser

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
    "world_lang": ["global_ai_news"],
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
    "forums": [],
}

KEYED_HOSTS = {"api.twitter.com", "api.x.com", "www.googleapis.com", "newsapi.org"}
KEYED_PARAMS = ("key=", "apikey", "api_key", "token=")


def check(failures, cond, msg):
    if not cond:
        failures.append(msg)


def main():
    failures, cases = [], 0

    # run_daily_pipeline.py imports the scraper as tools.scrape_rss_feeds, from the
    # project root, where its bare sibling imports (feed_sources, web_text) need
    # the module to put its own directory on the path.
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    r = subprocess.run([sys.executable, "-c", "import tools.scrape_rss_feeds"], cwd=root,
                       capture_output=True, text=True)
    cases += 1
    check(failures, r.returncode == 0,
          f"tools.scrape_rss_feeds does not import from the root: {r.stderr.strip()[-200:]}")
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

    cases += scraper_cases(failures)

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


def rss_fixture(items, now):
    """An RSS document whose items are (title, summary) pairs dated one hour before now."""
    stamp = format_datetime(now - timedelta(hours=1))
    body = "".join(
        f"<item><title>{t}</title><link>https://example.com/{i}</link>"
        f"<description>{s}</description><pubDate>{stamp}</pubDate></item>"
        for i, (t, s) in enumerate(items))
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>{body}</channel></rss>'


def scraper_cases(failures):
    """Task 4: relevance filters, link clean-up, company routing, category inheritance."""
    sc = scrape_rss_feeds
    cases = 0
    mentions_ai = getattr(sc, "mentions_ai", None)
    musk_on_ai = getattr(sc, "musk_on_ai", None)
    if not (mentions_ai and musk_on_ai and hasattr(sc, "articles_from_feed")
            and hasattr(sc, "unwrap_bing") and hasattr(sc, "route_by_title")):
        failures.append("scraper lacks mentions_ai / musk_on_ai / articles_from_feed / "
                        "unwrap_bing / route_by_title")
        return 1

    # ── The AI filter on general-interest feeds ──────────────────────────────
    for title in ("OpenAI ships GPT-6.1 Sol", "Why A.I. agents fail", "A new LLM tops the benchmark"):
        cases += 1
        check(failures, mentions_ai(title), f"mentions_ai missed an AI headline: {title!r}")
    for title in ("Nothing Phone (4a) gets a sale date", "Tesla deliveries fell 2%",
                  "Real estate agents brace for a rate cut"):
        cases += 1
        check(failures, not mentions_ai(title), f"mentions_ai kept a non-AI headline: {title!r}")

    # ── The Musk filter: Musk talking about AI or autonomy ───────────────────
    for title in ("Elon Musk says FSD will be unsupervised this year",
                  "Musk: Grok 5 has a shot at AGI"):
        cases += 1
        check(failures, musk_on_ai(title), f"musk_on_ai missed: {title!r}")
    for title in ("Tesla deliveries beat Wall Street guesses", "Elon Musk's pay package goes to a vote"):
        cases += 1
        check(failures, not musk_on_ai(title), f"musk_on_ai kept: {title!r}")

    # ── articles_from_feed applies the flag of the feed it reads ─────────────
    now = datetime.now(timezone.utc)
    feed = feedparser.parse(rss_fixture([
        ("OpenAI ships a cheaper reasoning model", "The new model costs half as much."),
        ("Nothing Phone (4a) gets a sale date", "The phone goes on sale next week."),
    ], now))
    cutoff = now - timedelta(hours=22)
    with contextlib.redirect_stdout(io.StringIO()):
        bbc = sc.articles_from_feed("BBC Technology", feed, cutoff)
        verge = sc.articles_from_feed("The Verge AI", feed, cutoff)
    cases += 2
    check(failures, len(bbc) == 1 and "OpenAI" in bbc[0]["title"],
          f"BBC Technology carries the ai flag, so only the AI story stays: {[a['title'] for a in bbc]}")
    check(failures, len(verge) == 2, f"The Verge AI is unfiltered, both stay: {len(verge)}")

    # ── Bing tracking links resolve to the publisher ─────────────────────────
    bing = ("http://www.bing.com/news/apiclick.aspx?ref=FexRss&aid=&tid=abc"
            "&url=https%3a%2f%2fexample.com%2fstory&c=1")
    cases += 2
    check(failures, sc.unwrap_bing(bing) == "https://example.com/story",
          f"unwrap_bing: {sc.unwrap_bing(bing)!r}")
    check(failures, sc.unwrap_bing("https://example.com/plain") == "https://example.com/plain",
          "a plain link must pass through unwrap_bing unchanged")

    # ── Company routing by headline, pooled groups only ──────────────────────
    for category, title, expected in (
        ("general", "OpenAI fires three safety researchers", "openai"),
        ("general", "Anthropic signs Google cloud deal", "anthropic_claude"),
        ("indian", "OpenAI opens Bengaluru office", "indian"),
    ):
        got = sc.route_by_title({"title": title, "category": category})["category"]
        cases += 1
        check(failures, got == expected, f"route_by_title({title!r}, {category}) -> {got}, want {expected}")

    # ── The kept copy inherits the most specific group ───────────────────────
    headline = "OpenAI fires three safety researchers over leak"
    publisher = {"title": headline, "url": "https://example.com/p", "source": "The Verge AI",
                 "category": "general", "summary": "A long publisher summary. " * 10}
    proxy = {"title": headline + " - Reuters", "url": "https://news.google.com/x",
             "source": "OpenAI (via Google News)", "category": "openai", "summary": ""}
    kept, removed = sc.deduplicate_stories([publisher, proxy])
    cases += 3
    check(failures, len(kept) == 1 and removed == 1, f"two copies of one story: kept {len(kept)}")
    check(failures, kept and kept[0]["source"] == "The Verge AI",
          f"the publisher's copy must be kept: {kept and kept[0]['source']}")
    check(failures, kept and kept[0]["category"] == "openai",
          f"the kept copy must take the OpenAI group: {kept and kept[0]['category']}")

    news = {"title": "AI hackathon winners shape the new city budget plan", "url": "https://example.com/n",
            "source": "The Verge AI", "category": "general", "summary": "News. " * 20}
    opp = {"title": "AI hackathon winners shape the new city budget plan", "url": "https://example.com/o",
           "source": "AI Hackathons (via Google News)", "category": "opportunity",
           "summary": "", "is_opportunity": False}
    kept, _ = sc.deduplicate_stories([news, opp])
    cases += 1
    check(failures, kept and kept[0]["category"] != "opportunity",
          f"a copy that failed the opportunity gate must not pull news into it: {kept and kept[0]['category']}")

    # One Google News link found by two searches: the opportunity search sits first in
    # the registry and its copy fails the gate. The OpenAI group must still get it,
    # and a second search finding the same link is not a second outlet.
    link = "https://news.google.com/rss/articles/CBMiSAME"
    first = {"title": "OpenAI commits $50 million AI fund to nonprofits - Reuters", "url": link,
             "source": "AI Grants (via Google News)", "category": "opportunity",
             "is_opportunity": False, "summary": ""}
    # Its headline differs too, so only the link can join the two.
    second = dict(first, title="Nonprofits get a new fund - Reuters",
                  source="OpenAI (via Google News)", category="openai")
    kept, removed = sc.deduplicate_stories([first, second])
    cases += 3
    check(failures, len(kept) == 1 and removed == 1, f"one link twice: kept {len(kept)}")
    check(failures, kept and kept[0]["category"] == "openai",
          f"a shared link must reach the OpenAI group: {kept and kept[0]['category']}")
    check(failures, kept and "duplicate_count" not in kept[0],
          f"one link found twice is not corroboration: {kept and kept[0].get('duplicate_count')}")

    # The same arXiv paper cross-listed in two feeds: one copy, in the quantum group.
    paper = {"title": "Learned noise models for quantum error correction",
             "url": "https://arxiv.org/abs/2610.01234", "source": "arXiv cs.LG",
             "category": "ai_research", "summary": "Abstract."}
    kept, _ = sc.deduplicate_stories([paper, dict(paper, source="arXiv quant-ph", category="quantum")])
    cases += 1
    check(failures, len(kept) == 1 and kept[0]["category"] == "quantum",
          f"a cross-listed paper must print once, as quantum: {[k['category'] for k in kept]}")

    # A stale opportunity copy that failed the gate must not stand in for today's news.
    stale = {"title": "IndiaAI Mission invites applications from AI startups for compute subsidy scheme",
             "url": "https://news.google.com/rss/articles/old", "source": "AI Grants (via Google News)",
             "category": "opportunity", "is_opportunity": False, "summary": "",
             "published": "2026-09-12T08:00:00+00:00"}
    fresh = {"title": "IndiaAI Mission extends deadline for startup applications",
             "url": "https://news.google.com/rss/articles/new", "source": "India AI (via Google News)",
             "category": "indian", "summary": "", "published": "2026-10-02T06:00:00+00:00"}
    kept, _ = sc.deduplicate_stories([stale, fresh])
    cases += 1
    check(failures, len(kept) == 1 and kept[0]["published"] == fresh["published"],
          f"the kept copy must be today's: {[k.get('published') for k in kept]}")

    # Hugging Face items share "hugging face" in every title; models are never merged.
    created = (now - timedelta(hours=3)).isoformat().replace("+00:00", "Z")
    ids = ["meta-llama/Llama-4.1-8B-Instruct", "Qwen/Qwen3.5-7B-Instruct",
           "unsloth/Qwen3.5-7B-Instruct-GGUF", "deepseek-ai/DeepSeek-V4-Base",
           "mistralai/Ministral-3-8B-Base", "nvidia/Nemotron-Nano-9B-v2", "nvidia/parakeet-tdt-0.6b-v3"]
    models = sc.parse_hf_models([{"id": i, "createdAt": created} for i in ids],
                                "Hugging Face new models", now - timedelta(hours=24))
    funding = {"title": "Hugging Face raises $400M led by Nvidia", "url": "https://example.com/hf",
               "source": "TechCrunch AI", "category": "business", "summary": "Funding. " * 20}
    kept, removed = sc.deduplicate_stories(models + [funding])
    cases += 1
    check(failures, removed == 0 and len(kept) == len(ids) + 1,
          f"{removed} Hugging Face items merged away: {[k['title'] for k in kept]}")

    # ── The PDF names a Bing item's outlet, not "via Bing News" ──────────────
    import builder_helpers
    saved, builder_helpers._ARTS = builder_helpers._ARTS, [{
        "title": "OpenAI raises again", "url": "https://example.com/story",
        "source": "OpenAI (via Bing News)", "publisher": "Reuters",
        "published": now.isoformat(), "published_date": now.strftime("%Y-%m-%d")}]
    try:
        s = builder_helpers.S(0, "Summary.", 4, ["openai"])
    finally:
        builder_helpers._ARTS = saved
    cases += 1
    check(failures, s["source"] == "Reuters", f"S() source for a Bing item: {s['source']!r}")

    # ── The non-RSS readers' pure parsers ────────────────────────────────────
    cases += reader_cases(failures, now)
    return cases


def reader_cases(failures, now):
    sc = scrape_rss_feeds
    cases = 0
    rel = getattr(sc, "relative_to_datetime", None)
    if not rel:
        failures.append("scraper lacks relative_to_datetime")
        return 1
    cases += 4
    check(failures, rel("13h ago", now) == now - timedelta(hours=14), f"13h ago -> {rel('13h ago', now)}")
    check(failures, rel("5 minutes ago", now) == now - timedelta(minutes=6),
          f"5 minutes ago -> {rel('5 minutes ago', now)}")
    check(failures, rel("2 days ago", now) is None, "days must return None")
    check(failures, rel("3 months ago", now) is None, "months must return None")

    cutoff = now - timedelta(hours=22)
    fresh = int((now - timedelta(hours=2)).timestamp())
    old = int((now - timedelta(hours=40)).timestamp())
    hn = {"hits": [
        {"title": "Show HN: An open LLM that runs on a phone", "url": "https://example.com/llm",
         "points": 300, "num_comments": 120, "created_at_i": fresh, "objectID": "1"},
        {"title": "A history of the shipping container", "url": "https://example.com/ship",
         "points": 500, "num_comments": 80, "created_at_i": fresh, "objectID": "2"},
        {"title": "Ask HN: Is AGI close?", "url": None,
         "points": 200, "num_comments": 400, "created_at_i": fresh, "objectID": "3"},
        {"title": "Old AI story", "url": "https://example.com/old",
         "points": 900, "num_comments": 9, "created_at_i": old, "objectID": "4"},
    ]}
    got = sc.parse_hn(hn, "Hacker News", cutoff)
    cases += 3
    check(failures, [a["title"] for a in got] == ["Show HN: An open LLM that runs on a phone",
                                                  "Ask HN: Is AGI close?"],
          f"Hacker News keeps fresh AI stories only: {[a['title'] for a in got]}")
    check(failures, len(got) == 2 and got[1]["url"] == "https://news.ycombinator.com/item?id=3",
          "a text post links to its Hacker News thread")
    check(failures, got and got[0]["category"] == "social", "Hacker News feeds the social group")

    hf = [
        {"id": "acme/tiny-7b", "createdAt": (now - timedelta(hours=3)).isoformat().replace("+00:00", "Z"),
         "likes": 120, "downloads": 4000},
        {"id": "acme/old-70b", "createdAt": (now - timedelta(days=9)).isoformat().replace("+00:00", "Z"),
         "likes": 900, "downloads": 90000},
    ]
    got = sc.parse_hf_models(hf, "Hugging Face new models", cutoff)
    cases += 2
    check(failures, [a["url"] for a in got] == ["https://huggingface.co/acme/tiny-7b"],
          f"only models created inside the window survive: {[a['url'] for a in got]}")
    check(failures, got and got[0]["title"] == "New on Hugging Face: acme/tiny-7b"
          and got[0]["category"] == "open_model", f"model record: {got and got[0]}")

    data = {"contents": [{"videoRenderer": {
        "videoId": "abc123", "title": {"runs": [{"text": "Musk on Grok 5 and AGI"}]},
        "publishedTimeText": {"simpleText": "3 hours ago"},
        "ownerText": {"runs": [{"text": "Some Channel"}]}}},
        {"videoRenderer": {
            "videoId": "old1", "title": {"runs": [{"text": "Older video"}]},
            "publishedTimeText": {"simpleText": "2 days ago"},
            "ownerText": {"runs": [{"text": "Other"}]}}}]}
    page = f"<script>var ytInitialData = {json.dumps(data)};</script>"
    got = sc.parse_yt_search(page, "YouTube search: Elon Musk AI", cutoff, now)
    cases += 3
    check(failures, [a["url"] for a in got] == ["https://www.youtube.com/watch?v=abc123"],
          f"YouTube search keeps the dated, fresh video: {[a['url'] for a in got]}")
    check(failures, got and got[0]["category"] == "elon_musk",
          "a reader's articles take the reader's group")
    check(failures, sc.parse_yt_search("<html>no data</html>", "YouTube search: AI news", cutoff, now) == [],
          "a page without ytInitialData returns no articles")
    return cases


if __name__ == "__main__":
    sys.exit(main())
