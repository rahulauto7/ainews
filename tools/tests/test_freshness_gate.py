"""Cases for the hard 24-hour freshness rule.

The 2026-09-17 edition shipped 34 of its 44 news stories older than 24 hours at
the moment it landed in the inbox. Nothing was wrong with the scraper: it cut at
24h from `scraped_at` (00:04 UTC), but the edition was not mailed until 15:39
UTC, so the window had aged 15.6 hours by delivery. Two further leaks:
quantum sources ran a 7-day window, shipping stories dated three days back, and
`analyzed_content.json` kept only `published_date`, so no downstream check could
see a time at all and measure the age.

The rule is measured at SEND time, not at scrape time, because the inbox is
where the reader meets it.

The two opportunity sections are exempt: a hackathon is dated by the DEADLINE it
is still open against, not by the day it was announced. Cutting those to 24h
emptied the section outright on 2026-09-07.

Run: python3 tools/tests/test_freshness_gate.py
"""

import contextlib
import io
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import builder_helpers
import check_quality
import scrape_rss_feeds
from builder_helpers import O, S
from check_quality import check_edition

NOW = datetime(2026, 9, 17, 15, 39, tzinfo=timezone.utc)

ARTICLES = [
    # 0: comfortably inside the window
    {"title": "Anthropic ships Claude Code hooks", "url": "https://example.com/a",
     "source": "The Verge", "summary": "...", "category": "general",
     "published": (NOW - timedelta(hours=3)).isoformat(), "published_date": "2026-09-17"},
    # 1: 37h old - inside the window at scrape, stale by the time it is sent
    {"title": "Qwen 3 weights land on Hugging Face", "url": "https://example.com/b",
     "source": "VentureBeat", "summary": "...", "category": "open_model",
     "published": (NOW - timedelta(hours=37)).isoformat(), "published_date": "2026-09-16"},
]

SUMMARY = "A plain-language summary of the story that runs long enough to clear the minimum. " * 9


def check(failures, ok, message):
    if not ok:
        failures.append(message)


def story(published_at=None, published_date=None, title="A story"):
    s = {"title": title, "summary": SUMMARY, "source": "The Verge",
         "url": "https://example.com/x", "relevance": 5, "tags": ["ai"]}
    if published_at:
        s["published_at"] = published_at
    if published_date:
        s["published_date"] = published_date
    return s


def codes(findings, code):
    return [f for f in findings if f["code"] == code]


def main():
    failures = []
    cases = 0
    builder_helpers._ARTS = ARTICLES  # offline: no rss_articles.json read

    # ── S() must carry the full timestamp, not just the date ──────────────────
    fresh = S(0, SUMMARY, 5, ["ai"])
    cases += 2
    check(failures, fresh.get("published_date") == "2026-09-17",
          f"S() must keep published_date for the PDF, got {fresh.get('published_date')!r}")
    check(failures, fresh.get("published_at") == ARTICLES[0]["published"],
          f"S() must copy the full published timestamp into published_at, "
          f"got {fresh.get('published_at')!r}")

    # ── the gate itself ───────────────────────────────────────────────────────
    data = {"sections": {"global_ai_news": [
        story(published_at=(NOW - timedelta(hours=23)).isoformat(), title="Fresh"),
    ]}}
    cases += 1
    check(failures, not codes(check_edition(data, now=NOW), "stale_story"),
          "a 23h-old story must pass the 24h gate")

    data = {"sections": {"global_ai_news": [
        story(published_at=(NOW - timedelta(hours=25)).isoformat(), title="Stale"),
    ]}}
    found = codes(check_edition(data, now=NOW), "stale_story")
    cases += 2
    check(failures, len(found) == 1,
          f"a 25h-old story must raise stale_story, got {found}")
    check(failures, found and found[0]["severity"] == "ERROR",
          f"stale_story must block the send (ERROR), got {found and found[0]['severity']}")

    # The exact failure of the 2026-09-17 edition: fine at scrape, stale at send.
    data = {"sections": {"open_model_landscape": [
        story(published_at=ARTICLES[1]["published"], title="Aged in the pipeline"),
    ]}}
    cases += 1
    check(failures, len(codes(check_edition(data, now=NOW), "stale_story")) == 1,
          "a story that went stale between scrape and send must be caught")

    # ── opportunities are exempt ──────────────────────────────────────────────
    for key in ("ai_hackathons", "product_showcase_opportunities"):
        data = {"sections": {key: [
            story(published_at=(NOW - timedelta(days=20)).isoformat(), title="A hackathon"),
        ]}}
        cases += 1
        check(failures, not codes(check_edition(data, now=NOW), "stale_story"),
              f"{key} is dated by deadline and must be exempt from the 24h gate")

    # ── quantum runs a 7-day rule, every other news section 24h ──────────────
    # The section is weekly (Thursdays) and each issue has to cover the whole week
    # since the last one, so 24h would leave it empty or near-empty every time.
    # It is a wider rule, not an absent one: a quantum story still has a limit.
    data = {"sections": {"quantum_ai_research": [
        story(published_at=(NOW - timedelta(days=3)).isoformat(), title="Three days old"),
    ]}}
    cases += 1
    check(failures, not codes(check_edition(data, now=NOW), "stale_story"),
          "a 3-day-old quantum story is inside the 7-day quantum rule and must pass")

    data = {"sections": {"quantum_ai_research": [
        story(published_at=(NOW - timedelta(days=6, hours=23)).isoformat(), title="Just inside"),
    ]}}
    cases += 1
    check(failures, not codes(check_edition(data, now=NOW), "stale_story"),
          "a quantum story just under 7 days must pass")

    data = {"sections": {"quantum_ai_research": [
        story(published_at=(NOW - timedelta(days=8)).isoformat(), title="Over a week"),
    ]}}
    found = codes(check_edition(data, now=NOW), "stale_story")
    cases += 2
    check(failures, len(found) == 1,
          f"an 8-day-old quantum story breaches even the 7-day rule, got {found}")
    check(failures, found and "7" in found[0]["detail"],
          f"the quantum finding must cite the 7-day rule it broke, got "
          f"{found and found[0]['detail']!r}")

    # The wider quantum rule must not leak into any other section.
    data = {"sections": {"global_ai_news": [
        story(published_at=(NOW - timedelta(days=3)).isoformat(), title="Not quantum"),
    ]}}
    cases += 1
    check(failures, len(codes(check_edition(data, now=NOW), "stale_story")) == 1,
          "a 3-day-old story outside quantum is still stale under the 24h rule")

    # ── date-only fallback: generous, so it fires only when unambiguous ───────
    data = {"sections": {"global_ai_news": [story(published_date="2026-09-16", title="Yesterday")]}}
    cases += 1
    check(failures, not codes(check_edition(data, now=NOW), "stale_story"),
          "a date-only story from yesterday could have been published late in the day, "
          "so it must not be flagged on the date alone")

    data = {"sections": {"global_ai_news": [story(published_date="2026-09-14", title="Three days")]}}
    cases += 1
    check(failures, len(codes(check_edition(data, now=NOW), "stale_story")) == 1,
          "a date-only story three days back is stale under any reading of the day")

    # ── build-time feedback, so the curator sees it before the send ───────────
    sections = {k: [] for k in ("ai_hackathons", "product_showcase_opportunities")}
    sections["global_ai_news"] = [
        story(published_at=(NOW - timedelta(hours=50)).isoformat(), title="WayTooOld"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            builder_helpers.write_analyzed(
                sections, out_file=os.path.join(tmp, "analyzed_content.json"))
        printed = buf.getvalue()
    cases += 1
    check(failures, "WayTooOld" in printed and "stale" in printed.lower(),
          f"write_analyzed must flag a stale pick at build time, printed:\n{printed}")

    # Build time must use each section's own rule, as the send gate does. On
    # 2026-10-01 write_analyzed measured quantum against the flat 24h limit and
    # flagged two stories (109h, 138h) that the 7-day send gate passes. write_analyzed
    # reads the real clock, so these ages are relative to it, not to NOW.
    real_now = datetime.now(timezone.utc)
    sections = {k: [] for k in ("ai_hackathons", "product_showcase_opportunities")}
    sections["quantum_ai_research"] = [
        story(published_at=(real_now - timedelta(hours=110)).isoformat(), title="WeekOldQuantum"),
        story(published_at=(real_now - timedelta(hours=200)).isoformat(), title="TooOldQuantum"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            builder_helpers.write_analyzed(
                sections, out_file=os.path.join(tmp, "analyzed_content.json"))
        printed = buf.getvalue()
    stale_lines = [l for l in printed.splitlines() if "stale" in l.lower()]
    cases += 2
    check(failures, not any("WeekOldQuantum" in l for l in stale_lines),
          f"a 110h quantum story is inside its 7-day rule and must not be flagged:\n{printed}")
    check(failures, any("TooOldQuantum" in l for l in stale_lines),
          f"a 200h quantum story is past its 7-day rule and must be flagged:\n{printed}")

    # ── the scraper must not widen the window behind the gate's back ──────────
    cases += 2
    check(failures, scrape_rss_feeds.NEWS_RULE_HOURS == 24,
          f"the rule the reader gets is 24h, got {scrape_rss_feeds.NEWS_RULE_HOURS}")
    check(failures, scrape_rss_feeds.QUANTUM_RULE_HOURS == 24 * 7,
          f"quantum keeps a 7-day rule, got {scrape_rss_feeds.QUANTUM_RULE_HOURS}")

    # The scrape window must be SHORTER than the rule by the time the run needs to
    # curate, render and send. Anchored at scrape time and cut at a full 24h, the
    # oldest item is already 24h old before curation starts and is guaranteed to
    # breach the rule by the time it is mailed - which is what happened on
    # 2026-09-17, when the send came 15.6h after the scrape.
    scrape_window = scrape_rss_feeds.window_hours_for("The Verge AI")
    cases += 2
    check(failures, scrape_window < scrape_rss_feeds.NEWS_RULE_HOURS,
          f"scrape window ({scrape_window}h) must leave room for the run to finish "
          f"inside the {scrape_rss_feeds.NEWS_RULE_HOURS}h rule")
    check(failures,
          scrape_window == scrape_rss_feeds.NEWS_RULE_HOURS
                           - scrape_rss_feeds.BUILD_ALLOWANCE_HOURS,
          "the scrape window must be the rule minus the build allowance")

    # A run that finishes inside the allowance must not trip its own gate.
    scraped = NOW - timedelta(hours=scrape_rss_feeds.BUILD_ALLOWANCE_HOURS)
    oldest = story(published_at=(scraped - timedelta(hours=scrape_window)).isoformat(),
                   title="Oldest item the scrape allows")
    cases += 1
    check(failures, not codes(check_edition({"sections": {"global_ai_news": [oldest]}},
                                            now=NOW), "stale_story"),
          "the oldest article the scraper accepts must still pass the gate when the "
          "run sends within its build allowance")

    q_window = scrape_rss_feeds.window_hours_for("Quantum + AI (via Google News)")
    cases += 1
    check(failures,
          q_window == scrape_rss_feeds.QUANTUM_RULE_HOURS
                      - scrape_rss_feeds.BUILD_ALLOWANCE_HOURS,
          f"the quantum scrape window must reserve the build allowance too, got {q_window}h")

    # Opportunities keep their wide window: they are dated by deadline.
    cases += 1
    check(failures, scrape_rss_feeds.window_hours_for("AI Hackathons (via Google News)") == 24 * 30,
          "opportunity sources keep the 30-day window")

    cases += 1
    check(failures, check_quality.STALE_HOURS == 24,
          f"the rule is 24 hours, got {getattr(check_quality, 'STALE_HOURS', None)}")

    # ── the pre-send report must state the age of the oldest story ───────────
    data = {"sections": {
        "global_ai_news": [story(published_at=(NOW - timedelta(hours=5)).isoformat()),
                           story(published_at=(NOW - timedelta(hours=19)).isoformat())],
        # Opportunities are exempt and must not be mistaken for the oldest story.
        "ai_hackathons": [story(published_at=(NOW - timedelta(days=20)).isoformat())],
    }}
    cases += 1
    check(failures, abs(check_quality.oldest_story_hours(data, now=NOW) - 19) < 0.01,
          f"oldest_story_hours must ignore opportunities, got "
          f"{check_quality.oldest_story_hours(data, now=NOW)}")

    cases += 1
    check(failures, check_quality.oldest_story_hours({"sections": {}}, now=NOW) is None,
          "oldest_story_hours must return None when nothing carries a date")

    # Quantum runs a different rule, so folding it into one "oldest news story"
    # number would report a legal 6-day quantum paper against the 24h rule and
    # read like a breach every Thursday.
    data = {"sections": {
        "global_ai_news": [story(published_at=(NOW - timedelta(hours=19)).isoformat())],
        "quantum_ai_research": [story(published_at=(NOW - timedelta(days=6)).isoformat())],
    }}
    cases += 1
    check(failures, abs(check_quality.oldest_story_hours(data, now=NOW) - 19) < 0.01,
          f"oldest_story_hours covers the 24h sections only, got "
          f"{check_quality.oldest_story_hours(data, now=NOW)}")

    lines = check_quality.freshness_lines(data, now=NOW)
    cases += 3
    check(failures, len(lines) == 2,
          f"one freshness line per rule in play, got {lines}")
    check(failures, any(l["limit"] == 24 and abs(l["oldest"] - 19) < 0.01 for l in lines),
          f"the 24h rule line must report 19h, got {lines}")
    check(failures, any(l["limit"] == 24 * 7 and abs(l["oldest"] - 144) < 0.01 for l in lines),
          f"the quantum line must report 144h against its own 7-day rule, got {lines}")

    cases += 1
    check(failures, check_quality.freshness_lines({"sections": {}}, now=NOW) == [],
          "no dated stories means no freshness lines")

    # One rule, one number. The scraper sizes its window against the rule and the
    # linter enforces it; if the two constants drift the window silently stops
    # matching the promise, which is exactly the class of bug this file exists for.
    cases += 1
    check(failures, scrape_rss_feeds.NEWS_RULE_HOURS == check_quality.STALE_HOURS,
          f"scraper rule ({scrape_rss_feeds.NEWS_RULE_HOURS}h) and linter rule "
          f"({check_quality.STALE_HOURS}h) must be the same number")
    cases += 1
    check(failures,
          scrape_rss_feeds.QUANTUM_RULE_HOURS == check_quality.SECTION_STALE_HOURS["quantum_ai_research"],
          "scraper and linter must agree on the quantum rule too")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
