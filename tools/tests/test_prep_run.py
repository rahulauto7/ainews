"""Cases for prep_run.py, which collapses the pre-curation setup into one turn.

The 2026-09-17 run spent turns 4-38 on this: reading the 41 KB workflow in four
chunks, re-reading three tool docstrings, polling a detached scraper four times,
running the tests and checking the date - 35 model turns before a single story
was read.

Two pieces here carry logic worth pinning down. scrape_is_fresh() decides whether
a re-run re-hits 34 feeds: a second run the same morning must not, a run the next
day must. case_count() reads the test suite's own output, and has to survive a
failing file dumping a traceback into the same report.

Run: python3 tools/tests/test_prep_run.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import web_text
from prep_run import case_count, scrape_is_fresh


def check(failures, ok, msg):
    if not ok:
        failures.append(msg)


def fake_scrape(hours_ago, n=498):
    """Stand in for web_text.load_articles() with a scrape of a given age."""
    when = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    return lambda: ({"scraped_at": when}, [{"title": f"a{i}"} for i in range(n)])


def main():
    failures, cases = [], 0
    real_loader = web_text.load_articles
    try:
        # A re-run twenty minutes later reuses the scrape on disk.
        web_text.load_articles = fake_scrape(0.3)
        fresh, n, _ = scrape_is_fresh()
        cases += 2
        check(failures, fresh, "a 20-minute-old scrape was not treated as fresh")
        check(failures, n == 498, f"article count not reported: {n}")

        # Tomorrow's run must re-scrape: yesterday's articles are not today's news.
        web_text.load_articles = fake_scrape(20)
        cases += 1
        check(failures, not scrape_is_fresh()[0], "a 20-hour-old scrape was reused")

        # The boundary belongs to the caller, not to a hardcoded six.
        web_text.load_articles = fake_scrape(8)
        cases += 2
        check(failures, not scrape_is_fresh()[0], "8h reused at the default 6h limit")
        check(failures, scrape_is_fresh(max_age_hours=12)[0],
              "8h rejected when the caller allowed 12h")

        # No scrape on disk at all - the first run of the day, or a cleared .tmp.
        def missing():
            raise FileNotFoundError(".tmp/rss_articles.json")

        web_text.load_articles = missing
        cases += 1
        check(failures, scrape_is_fresh() == (False, 0, None),
              "a missing scrape file did not report as not-fresh")

        # A half-written scrape file: json parsed, but no timestamp to age.
        web_text.load_articles = lambda: ({}, [])
        cases += 1
        check(failures, not scrape_is_fresh()[0], "a scrape with no scraped_at was reused")
    finally:
        web_text.load_articles = real_loader

    # case_count() reads run_tests()'s report lines, which look like
    # "    test_x.py    19/19 passed".
    passing = ["    test_check_quality.py           19/19 passed",
               "    test_curation_tools.py          15/15 passed"]
    cases += 1
    check(failures, case_count(passing) == 34, f"expected 34 cases, got {case_count(passing)}")

    # When a file fails, run_tests() appends 600 characters of its stdout to the
    # same list. Those lines have no count in them, and the arithmetic used to
    # crash on the traceback rather than report the failure it was called about.
    noisy = passing + [
        "    test_story_dates.py             2 failure(s) of 14",
        "      Traceback (most recent call last): AssertionError: 3/4 passed here",
    ]
    cases += 1
    try:
        got = case_count(noisy)
        check(failures, got == 34, f"failure dump miscounted: expected 34, got {got}")
    except Exception as e:  # noqa: BLE001 - the regression is any raise at all
        check(failures, False, f"case_count crashed on a failure dump: {e!r}")

    cases += 1
    check(failures, case_count([]) == 0, "an empty report did not count zero")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
