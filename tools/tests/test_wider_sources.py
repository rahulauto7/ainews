"""Cases for the wider source net and reading a story somewhere else.

rahul, 2026-10-03: "Search everywhere on the internet wherever possible. If they
are asking for any API ... don't use that platform." So the registry grew from
218 to 390 keyless sources (regional and non-English Google News editions,
mainstream and trade press, science explainers, podcasts, Reddit, Bluesky), and
the same day he asked for every story explained so fully that he never has to
look elsewhere. A story whose own publisher blocks the fetch (Reuters, NYT,
Techmeme, paywalls) is now read from another outlet carrying it.

All cases are offline. Run: python3 tools/tests/test_wider_sources.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import feedparser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fetch_articles
import feed_sources
import scrape_rss_feeds as sc
import web_text

NOW = datetime(2026, 10, 3, 6, 0, tzinfo=timezone.utc)


def check(failures, ok, message):
    if not ok:
        failures.append(message)


def feed_xml(items):
    """An RSS document; each item is (title or None, description, minutes ago, link)."""
    out = ['<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>']
    for title, desc, ago, link in items:
        when = (NOW - timedelta(minutes=ago)).strftime("%a, %d %b %Y %H:%M:%S +0000")
        out.append("<item>" + (f"<title>{title}</title>" if title else "")
                   + f"<description>{desc}</description><link>{link}</link>"
                   f"<pubDate>{when}</pubDate></item>")
    out.append("</channel></rss>")
    return "".join(out)


def main():
    failures, cases = [], 0
    cutoff = NOW - timedelta(hours=22)

    # ── 1. The registry: wider, still keyless, the opportunity feeds untouched ─
    names = [r[0] for r in feed_sources.RSS]
    cats = {r[2] for r in feed_sources.RSS}
    cases += 4
    check(failures, len(feed_sources.RSS) + len(feed_sources.EXTRA) >= 390,
          f"{len(feed_sources.RSS) + len(feed_sources.EXTRA)} sources; the 2026-10-03 net has 390")
    check(failures, {"world_lang", "forums"} <= cats, f"new groups missing: {cats}")
    langs = [n for n in names if n.startswith("AI in ")]
    check(failures, len(langs) >= 17, f"{len(langs)} non-English searches, expected 17 or more")
    check(failures, sum(1 for r in feed_sources.RSS if r[2] == "opportunity") == 6,
          "the opportunity feeds belong to the hackathon work and were not changed here")

    # ── 2. Untitled posts (Bluesky) get their opening words as a headline ─────
    cases += 3
    check(failures, sc.title_from_text("OpenAI shipped a model. It reads code.") ==
          "OpenAI shipped a model.", "the first sentence is the headline")
    long_title = sc.title_from_text("word " * 60)
    check(failures, len(long_title) <= 113 and long_title.endswith("..."),
          f"a long opening is cut between words: {long_title!r}")
    feed = feedparser.parse(feed_xml([(None, "Anthropic released Claude hooks today. More soon.",
                                       30, "https://bsky.app/profile/x/post/1")]))
    arts = sc.articles_from_feed("Ethan Mollick on Bluesky", feed, cutoff)
    check(failures, arts and arts[0]["title"] == "Anthropic released Claude hooks today.",
          f"an untitled post must be titled from its text: {arts and arts[0]['title']!r}")

    # ── 3. "top" keeps the first 20 of a regional edition's 100 results ──────
    top_name = "UK AI (via Google News)"
    feed = feedparser.parse(feed_xml([(f"AI story {i} - Outlet", "x", i, f"https://e.com/{i}")
                                      for i in range(60)]))
    cases += 2
    check(failures, top_name in sc.TOP_SOURCES, "regional editions carry the top flag")
    check(failures, len(sc.articles_from_feed(top_name, feed, cutoff)) == sc.TOP_PER_FEED,
          "a top source keeps only its first entries")

    # ── 4. A refused fetch is retried once with the browser User-Agent ───────
    calls = []

    class Resp:
        def __init__(self, code):
            self.status_code, self.content = code, feed_xml([("AI news", "x", 5, "https://e.com/a")])

        def raise_for_status(self):
            if self.status_code >= 400:
                raise sc.requests.exceptions.HTTPError(str(self.status_code))

    def fake_get(url, timeout=None, headers=None):
        calls.append(headers["User-Agent"])
        return Resp(503 if len(calls) == 1 else 200)

    saved_get, saved_sleep = sc.requests.get, sc.time.sleep
    sc.requests.get, sc.time.sleep = fake_get, lambda s: None
    try:
        got = sc.fetch_feed("TechCrunch AI", "https://e.com/feed", NOW - timedelta(days=3650))
    finally:
        sc.requests.get, sc.time.sleep = saved_get, saved_sleep
    cases += 2
    check(failures, len(got) == 1, f"a 503 then 200 must still read the feed: {len(got)}")
    check(failures, len(calls) == 2 and calls[1] == sc.BROWSER_UA,
          f"the retry must use the browser User-Agent: {calls}")

    # ── 5. De-duplication keeps the other outlets' links, forums last ────────
    def art(title, source, url, category="general", summary="s"):
        return {"title": title, "source": source, "url": url, "category": category,
                "summary": summary, "published": NOW.isoformat()}

    title = "OpenAI signs a chip deal with Broadcom for custom AI processors"
    kept, _ = sc.deduplicate_stories([
        art(title, "r/OpenAI", "https://reddit.com/r/OpenAI/1", "forums", "x" * 900),
        art(title + " - Reuters", "Reuters AI (via Google News)", "https://news.google.com/rss/articles/R"),
        art(title, "TechCrunch AI", "https://techcrunch.com/a", summary="y" * 300),
        art(title, "The Verge AI", "https://theverge.com/b", summary="z" * 200),
    ])
    cases += 4
    check(failures, len(kept) == 1, f"one story, {len(kept)} kept")
    best = kept[0]
    check(failures, best["source"] == "TechCrunch AI",
          f"a forum post must never be the copy kept over an outlet: {best['source']}")
    alt_sources = [a["source"] for a in best.get("alternates", [])]
    check(failures, set(alt_sources) == {"r/OpenAI", "Reuters AI (via Google News)", "The Verge AI"},
          f"every other copy's link is kept: {alt_sources}")
    check(failures, alt_sources[-1] == "Reuters AI (via Google News)",
          f"direct links come before proxy links: {alt_sources}")

    # Non-English headlines share their language's words for AI, so they are
    # never merged on title (Vietnamese "tri tue nhan tao" is four tokens).
    vi = [art("Trí tuệ nhân tạo giúp nông dân " + w, "AI in Vietnamese (via Google News)",
              f"https://vn.example/{i}", "world_lang") for i, w in enumerate(("trồng lúa", "bán cà phê"))]
    kept, _ = sc.deduplicate_stories(vi)
    cases += 1
    check(failures, len(kept) == 2, f"two Vietnamese stories merged into {len(kept)}")

    # ── 6. A blocked story is read from another outlet ───────────────────────
    pages = {
        "https://www.reuters.com/x": {"url": "https://www.reuters.com/x", "error": "FAILED: HTTPError: 401"},
        "https://thin.example/a": {"url": "https://thin.example/a", "error": None, "text": "Subscribe"},
        "https://open.example/b": {"url": "https://open.example/b", "error": None, "text": "Full story. " * 80,
                                   "final_url": "https://open.example/b"},
        "https://found.example/c": {"url": "https://found.example/c", "error": None, "text": "Found. " * 90},
    }
    saved_fetch, saved_search = fetch_articles.fetch_one, web_text.search_google_news
    fetch_articles.fetch_one = lambda url, cache: dict(pages[url])
    searched = []
    web_text.search_google_news = lambda q, days=3: (searched.append(q) or
                                                     [{"source": "Found", "url": "https://found.example/c",
                                                       "title": "t"}])
    try:
        article = {"title": "Nvidia to invest $5 billion in Intel - Reuters", "url": "https://www.reuters.com/x",
                   "alternates": [{"source": "Thin", "url": "https://thin.example/a"},
                                  {"source": "Open Outlet", "url": "https://open.example/b"}]}
        rec = fetch_articles.read_elsewhere(article, pages["https://www.reuters.com/x"], {})
        cases += 2
        check(failures, rec and rec["read_via"] == "Open Outlet",
              f"the first usable alternate must be read: {rec and rec.get('read_via')}")
        check(failures, not searched, "no search while an alternate works")

        article["alternates"] = [{"source": "Thin", "url": "https://thin.example/a"}]
        rec = fetch_articles.read_elsewhere(article, pages["https://www.reuters.com/x"], {})
        cases += 2
        check(failures, rec and rec["read_via"] == "Found (found by search)",
              f"with no usable alternate, a search finds one: {rec and rec.get('read_via')}")
        check(failures, searched and "Reuters" not in searched[0] and "Nvidia" in searched[0],
              f"the search uses the headline without its publisher: {searched}")
        line = fetch_articles.render("7", rec, 100, None)
        cases += 1
        check(failures, "read via Found" in line and "found.example/c" in line,
              f"the head line names the outlet and its URL: {line[:160]!r}")
    finally:
        fetch_articles.fetch_one, web_text.search_google_news = saved_fetch, saved_search

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
