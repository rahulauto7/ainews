"""Everything the curation step needs to start, in one call.

The 2026-09-17 run spent turns 4-38 getting here: reading the 41 KB workflow in
four chunks, re-reading builder_helpers and three tool docstrings, polling the
detached scraper four times, running the tests, and checking the date. Thirty-five
model turns of orientation, ~35k of context, before a single story was read.

This runs the slow parts to completion - nothing is detached, so nothing needs
polling - and prints one compact brief:

  - today, the weekday, and whether Quantum + AI is in (Thursdays only)
  - the section keys in render order, so they are never guessed
  - the last three editions on disk, for the duplicate-across-days check
  - the test suite result as one line
  - the scrape, then the digest, Devpost, the carry-forward recheck and the
    other hackathon platforms (lablab.ai, mlcontests, HackerEarth, Devfolio,
    Unstop, MLH, TAIKAI, Hackster), in parallel

Outputs land where they always do: .tmp/rss_articles.json, .tmp/digest.md,
.tmp/devpost.txt, .tmp/recheck.txt, and now .tmp/hackathons.txt.

Usage:
  python3 tools/prep_run.py               # full prep
  python3 tools/prep_run.py --no-scrape   # reuse today's scrape, rebuild the rest
"""

import argparse
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import web_text
from builder_helpers import prior_editions

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
QUANTUM_WEEKDAY = 3  # Thursday; scrape_rss_feeds.py owns the authoritative constant


def _run(name, args, out_file=None):
    """Run a tool to completion. Returns (name, returncode, tail-of-output)."""
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    text = (r.stdout or "") + (r.stderr or "")
    if out_file:
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(text)
    return name, r.returncode, text


def scrape_is_fresh(max_age_hours=6):
    """True when .tmp/rss_articles.json was written recently enough to reuse.

    A re-run inside the same morning should not re-hit 200+ sources; a run the next
    day must. Six hours splits those without a flag.
    """
    try:
        data, arts = web_text.load_articles()
    except (OSError, ValueError, KeyError):
        return False, 0, None
    try:
        scraped = datetime.fromisoformat(data["scraped_at"])
    except (KeyError, ValueError):
        return False, 0, None
    age = (datetime.now(scraped.tzinfo) - scraped).total_seconds() / 3600
    return age <= max_age_hours, len(arts), data["scraped_at"][:16]


def case_count(lines):
    """Total test cases in run_tests()'s report.

    A failing file appends 600 characters of its own stdout to the same list, and
    that dump can itself contain something shaped like a count - an assertion
    message quoting "3/4 passed" is enough to inflate the total. Only run_tests()'s
    own report lines count: four spaces, the file name, then the tally and nothing
    after it.
    """
    total = 0
    for line in lines:
        m = re.match(r" {4}\S+\.py\s+\d+/(\d+) passed\s*$", line)
        if m:
            total += int(m.group(1))
    return total


def task_line(name, rc, lines):
    """The brief's line for one opportunity task.

    find_opportunities platforms reports a failed platform as a "!! <platform>:
    <error>" line and carries on, so its exit code alone cannot say that lablab.ai
    or Devfolio went unread.
    """
    broken = [l[3:].split(":")[0] for l in lines if l.startswith("!! ")]
    return (f"  {name:10s} {len(lines)} lines -> .tmp/{name}.txt"
            + ("  !! failed" if rc != 0 else "")
            + (f"  !! unread: {', '.join(broken)}" if broken else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-scrape", action="store_true", help="reuse the scrape on disk")
    ap.add_argument("--skip-tests", action="store_true")
    args = ap.parse_args()
    start = time.time()

    from generate_pdf import SECTION_CONFIG, SECTION_ORDER

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    quantum = now.weekday() == QUANTUM_WEEKDAY
    print(f"RUN {today} ({now.strftime('%A')})  |  "
          f"Quantum + AI: {'IN (Thursday)' if quantum else 'OUT (not Thursday)'}  |  "
          f"{len(SECTION_ORDER) - (0 if quantum else 1)} sections")

    print("\nSection keys, in render order:")
    for i, key in enumerate(SECTION_ORDER, 1):
        note = "  <- skip today" if key == "quantum_ai_research" and not quantum else ""
        print(f"  {i:2d}. {key:34s} {SECTION_CONFIG[key]['label']}{note}")

    editions = prior_editions(today)
    print(f"\nPrior editions on disk (duplicate-across-days check): "
          f"{', '.join(d for d, _ in editions) or 'none'}")
    for date, ed in editions[:1]:
        counts = {k: len(v or []) for k, v in (ed.get("sections") or {}).items()}
        print(f"  {date}: {sum(counts.values())} stories across {len(counts)} sections")

    fresh, n_arts, when = scrape_is_fresh()
    jobs = []
    if args.no_scrape or fresh:
        why = "--no-scrape" if args.no_scrape else f"fresh, scraped {when} UTC"
        print(f"\nScrape: reusing {n_arts} articles on disk ({why})")
    else:
        from feed_sources import EXTRA, RSS
        print(f"\nScrape: running {len(RSS) + len(EXTRA)} sources to completion...")
        name, rc, text = _run("scrape", [os.path.join(TOOLS_DIR, "scrape_rss_feeds.py")],
                              os.path.join(web_text.TMP_DIR, "rss_scrape.log"))
        tail = [l for l in text.strip().splitlines() if l.strip()][-2:]
        print("  " + " | ".join(l.strip() for l in tail))
        if rc != 0:
            print("  !! scrape failed - RSS is the only input source, so stop here")
            return 1

    # Devpost, the carry-forward recheck and the other hackathon platforms hit
    # different hosts than each other, the digest only needs the scrape already on
    # disk, and the test suite is pure CPU. All five run at once instead of five
    # polled turns.
    print("\nDigest + opportunity checks + tests, in parallel...")
    tasks = [
        ("digest", [os.path.join(TOOLS_DIR, "news_digest.py")], None),
        ("devpost", [os.path.join(TOOLS_DIR, "find_opportunities.py"), "devpost"],
         os.path.join(web_text.TMP_DIR, "devpost.txt")),
        ("recheck", [os.path.join(TOOLS_DIR, "find_opportunities.py"), "recheck"],
         os.path.join(web_text.TMP_DIR, "recheck.txt")),
        ("hackathons", [os.path.join(TOOLS_DIR, "find_opportunities.py"), "platforms"],
         os.path.join(web_text.TMP_DIR, "hackathons.txt")),
    ]

    from verify_edition import run_tests

    with ThreadPoolExecutor(max_workers=5) as ex:
        tests = None if args.skip_tests else ex.submit(run_tests)
        results = list(ex.map(lambda t: _run(t[0], t[1], t[2]), tasks))

        for name, rc, text in results:
            lines = [l for l in text.strip().splitlines() if l.strip()]
            if name == "digest":
                print(f"  digest     {lines[-1] if lines else 'no output'}")
            else:
                print(task_line(name, rc, lines))

        if tests is not None:
            ok, lines = tests.result()
            print(f"\nTests: {'all pass' if ok else 'FAILURES'} "
                  f"({case_count(lines)} cases across {len(lines)} files)")
            if not ok:
                print("\n".join(lines))
                return 1

    print(f"\nPrep done in {time.time() - start:.0f}s. Next:")
    print("  1. Read .tmp/digest.md")
    print("  2. python3 tools/fetch_articles.py IDX IDX ...   (one call, all indices)")
    print("  3. Write .tmp/build_analyzed_%s.py against builder_helpers" % today)
    print("  4. python3 tools/verify_edition.py --send")
    return 0


if __name__ == "__main__":
    sys.exit(main())
