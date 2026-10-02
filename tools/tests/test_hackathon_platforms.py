"""Cases for the hackathon platforms: lablab.ai, Devpost newest, Devfolio, Unstop.

lablab.ai has no API and no feed; its events sit in the page's Next.js data
chunks (self.__next_f.push). The fixture below is built the way the page is:
the records' text is JSON-escaped into one push call, with each record's keys in
the order seen on the real page on 2 Oct 2026.

Run: python3 tools/tests/test_hackathon_platforms.py
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import find_opportunities

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)


def check(failures, cond, msg):
    if not cond:
        failures.append(msg)


def record(name, slug, start, end, kind="HACKATHON", signup=True):
    return (f'{{"name":"{name}","description":"x","signupActive":{str(signup).lower()},'
            f'"oneCouponPerParticipant":false,"endAt":"{end}","startAt":"{start}",'
            f'"toBeAnnounced":false,"image":"/x.png","slug":"{slug}","previousSlugs":[],'
            f'"teamsActive":true,"type":"{kind}"}}')


def page(*records):
    payload = '1:["$","div",null,{"events":[' + ",".join(records) + "]}]"
    chunk = json.dumps(payload)[1:-1]
    return f'<html><script>self.__next_f.push([1,"{chunk}"])</script></html>'


def main():
    failures, cases = [], 0
    parse = getattr(find_opportunities, "parse_lablab_listing", None)
    if not parse:
        print("FAIL: find_opportunities.parse_lablab_listing does not exist")
        print("1 failure(s) of 1")
        return 1

    # ── 1. An ended event is dropped, an open one returned whole ─────────────
    html = page(
        record("Old Hack", "old-hack-2025", "2025-03-01T19:00:00.000Z", "2025-03-08T19:00:00.000Z"),
        record("AMD Developer Hackathon ACT III", "amd-developer-hackathon-act-iii",
               "2026-10-12T19:00:00.000Z", "2026-10-18T19:00:00.000Z"),
    )
    got = parse(html, NOW)
    cases += 2
    check(failures, len(got) == 1, f"only the open event: {got!r}")
    check(failures, got and got[0] == {"slug": "amd-developer-hackathon-act-iii", "start": "2026-10-12",
                                       "end": "2026-10-18", "signup": True},
          f"open event record: {got and got[0]!r}")

    # ── 2. No data chunks: nothing, and no exception ─────────────────────────
    cases += 1
    try:
        check(failures, parse("<html><body>Maintenance</body></html>", NOW) == [],
              "a page with no __next_f chunks must return []")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"a page with no __next_f chunks raised {exc!r}")

    # ── 3. Workshops are not hackathons ──────────────────────────────────────
    html = page(record("Agents Workshop", "agents-workshop", "2026-10-05T19:00:00.000Z",
                       "2026-10-06T19:00:00.000Z", kind="WORKSHOP"))
    cases += 1
    check(failures, parse(html, NOW) == [], "a WORKSHOP must be left out")

    # ── Soonest deadline first ───────────────────────────────────────────────
    html = page(
        record("Later", "later", "2026-11-01T19:00:00.000Z", "2026-11-08T19:00:00.000Z"),
        record("Sooner", "sooner", "2026-10-01T19:00:00.000Z", "2026-10-06T19:00:00.000Z", signup=False),
    )
    got = parse(html, NOW)
    cases += 2
    check(failures, [e["slug"] for e in got] == ["sooner", "later"], f"order: {got!r}")
    check(failures, got and got[0]["signup"] is False, "signupActive false must read as False")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
