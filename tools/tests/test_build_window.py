"""Cases for the AI Hackathons section's 7-day build rule.

rahul, 2026-10-03: "7 days is for build time ... exclude within 7 days
submissions deadline not registration deadline". So a hackathon is printed only
when its SUBMISSION deadline is at least seven days after the edition date. The
check runs twice: write_analyzed() reports it while the builder is open, and
check_quality blocks the send on it, because a curator under time pressure
carrying a hackathon forward from yesterday is exactly how one slips through.

Run: python3 tools/tests/test_build_window.py
"""

import contextlib
import io
import os
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import builder_helpers
import check_quality
from hackathon_sources import MIN_BUILD_DAYS, has_build_time, parse_deadline

TODAY = date(2026, 10, 3)
SUMMARY = ("A global online hackathon for teams building AI agents. Entrants submit a working demo "
           "and a short video. The organiser pays cash prizes to the top three teams. Anyone over "
           "eighteen can enter from any country. Judging runs for two weeks after the deadline. "
           "Teams of up to four people may enter, and solo entrants are welcome too. The brief asks "
           "for an agent that completes a real task for a small business, such as booking "
           "appointments, answering customer email or reconciling invoices. Each entry needs a public "
           "code repository, a three-minute video showing the agent at work and a short written "
           "description of how it was built. The organiser provides free cloud credits to every "
           "registered team, and mentors hold open office hours twice a week. Judges score entries "
           "on usefulness, technical quality, design and how clearly the team explains its work. "
           "Winners are announced in a live online session, and prize money is paid within thirty "
           "days of the announcement. Past winners have gone on to raise seed funding.")


def check(failures, cond, msg):
    if not cond:
        failures.append(msg)


def hackathon(title, deadline):
    story = {"title": title, "summary": SUMMARY, "source": "Devpost", "url": f"https://{title[:6]}.devpost.com/",
             "relevance": 5, "tags": ["hackathon"]}
    if deadline is not None:
        story["deadline"] = deadline
    return story


def main():
    failures, cases = [], 0

    cases += 1
    check(failures, MIN_BUILD_DAYS == 7, f"the rule is seven days, got {MIN_BUILD_DAYS}")

    # ── Reading the deadline as the curator writes it ────────────────────────
    for text, want in (
        ("23 Oct 2026", date(2026, 10, 23)),
        ("23 October 2026", date(2026, 10, 23)),
        ("Oct 23, 2026", date(2026, 10, 23)),
        ("October 23rd, 2026", date(2026, 10, 23)),
        ("2026-10-23", date(2026, 10, 23)),
        ("23 Oct 2026, 11:45 PM PT", date(2026, 10, 23)),
        ("Sep 01 - Oct 23, 2026", date(2026, 10, 23)),        # a range ends at its last date
        ("30 Oct", date(2026, 10, 30)),                        # no year: the coming one
        ("5 Jan", date(2027, 1, 5)),                           # ...which can be next year
        ("1 Oct", date(2026, 10, 1)),                          # two days ago is still this year
        ("Rolling", None),
        ("", None),
        (None, None),
        ("31 Feb 2026", None),
    ):
        cases += 1
        got = parse_deadline(text, TODAY)
        check(failures, got == want, f"parse_deadline({text!r}) = {got!r}, want {want!r}")

    # ── The boundary: seven days is enough, six is not ───────────────────────
    cases += 4
    check(failures, has_build_time(date(2026, 10, 10), TODAY), "exactly 7 days to build must pass")
    check(failures, not has_build_time(date(2026, 10, 9), TODAY), "6 days to build must fail")
    check(failures, not has_build_time(None, TODAY), "an unknown deadline cannot pass")
    check(failures, not has_build_time(date(2026, 10, 1), TODAY), "a passed deadline must fail")

    # ── The send gate ────────────────────────────────────────────────────────
    data = {"sections": {"ai_hackathons": [
        hackathon("Seven Days Hack", "10 Oct 2026"),
        hackathon("Six Days Hack", "9 Oct 2026"),
        hackathon("No Deadline Hack", None),
        hackathon("Vague Deadline Hack", "end of October"),
    ], "product_showcase_opportunities": [
        # Programmes keep the near-deadline rule: one closing tomorrow still prints.
        dict(hackathon("Fellowship Closing Tomorrow", "4 Oct 2026"), source="IAPS"),
    ]}}
    findings = check_quality.check_edition(data, today=TODAY.isoformat())
    by_title = {}
    for f in findings:
        if f["severity"] == "ERROR":
            by_title.setdefault(f["title"], []).append(f["code"])
    cases += 5
    check(failures, "Seven Days Hack" not in by_title, f"7 days left must not block: {by_title}")
    check(failures, by_title.get("Six Days Hack") == ["hackathon_too_soon"],
          f"6 days left must block as hackathon_too_soon: {by_title}")
    check(failures, by_title.get("No Deadline Hack") == ["hackathon_no_deadline"],
          f"a hackathon with no deadline must block: {by_title}")
    check(failures, by_title.get("Vague Deadline Hack") == ["hackathon_no_deadline"],
          f"an unreadable deadline must block: {by_title}")
    check(failures, "Fellowship Closing Tomorrow" not in by_title,
          f"the build rule is for hackathons only, not programmes: {by_title}")

    detail = next((f["detail"] for f in findings if f["title"] == "Six Days Hack"), "")
    cases += 1
    check(failures, "09 Oct 2026" in detail and "6 day" in detail,
          f"the finding must say when submissions close and how many days are left: {detail!r}")

    # ── The builder reports it while it is still open ────────────────────────
    # write_analyzed() dates the edition by the clock, so these are relative to it.
    soon, later = date.today() + timedelta(days=3), date.today() + timedelta(days=20)
    sections = {"ai_hackathons": [hackathon("Too Soon Hack", f"{soon:%d %b %Y}"),
                                  hackathon("Plenty Of Time Hack", f"{later:%d %b %Y}")]}
    saved, builder_helpers._ARTS = builder_helpers._ARTS, []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                builder_helpers.write_analyzed(sections, out_file=os.path.join(tmp, "analyzed_content.json"))
    finally:
        builder_helpers._ARTS = saved
    flagged = [l for l in buf.getvalue().splitlines() if "days left to build" in l]
    cases += 2
    check(failures, any("Too Soon Hack" in l and "3 day(s)" in l for l in flagged),
          f"write_analyzed must flag a hackathon closing in 3 days, flagged: {flagged}")
    check(failures, not any("Plenty Of Time Hack" in l for l in flagged),
          f"write_analyzed must not flag one with 20 days left, flagged: {flagged}")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
