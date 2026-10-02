"""Cases for the delivery email describing the edition it actually carries.

send_email.py shipped a hardcoded body claiming "15 sections including AI music
business, AI music & copyright updates" from 2026-04 until 2026-09-17. The brief
was cut to 12 sections on 2026-09-12 and has never covered AI music, so every
mail that did go out described an edition that did not exist. The body is now
derived from analyzed_content.json, which is the same file the PDF renders.

Run: python3 tools/tests/test_email_body.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from send_email import build_body, edition_summary

EDITION = {
    "analyzed_at": "2026-09-17T00:22:00+00:00",
    "sections": {
        "ai_hackathons": [{"title": f"H{n}"} for n in range(6)],
        "quantum_ai_research": [{"title": f"Q{n}"} for n in range(5)],
        "global_ai_news": [{"title": f"G{n}"} for n in range(6)],
    },
    "section_labels": {
        "ai_hackathons": "AI Hackathons",
        "product_showcase_opportunities": "AI Grants, Fellowships & Programs",
        "quantum_ai_research": "Quantum + AI",
        "global_ai_news": "Global AI News",
    },
}


def check(failures, ok, message):
    if not ok:
        failures.append(message)


def main():
    failures = []
    cases = 0

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "analyzed_content.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(EDITION, f)
        summary = edition_summary(path)
        missing = edition_summary(os.path.join(tmp, "nope.json"))

    # Counts come from the edition, not from a constant.
    cases += 2
    check(failures, summary["total_stories"] == 17,
          f"total_stories={summary['total_stories']} (expected 17)")
    check(failures, summary["section_count"] == 3,
          f"section_count={summary['section_count']} (expected 3, empty sections excluded)")

    # Sections are named by their display labels, in render order.
    cases += 2
    check(failures, summary["sections"][0] == ("AI Hackathons", 6),
          f"first section: {summary['sections'][0]!r}")
    check(failures, [n for n, _ in summary["sections"]] ==
          ["AI Hackathons", "Quantum + AI", "Global AI News"],
          f"render order wrong: {[n for n, _ in summary['sections']]!r}")

    # A section with no stories today (Quantum on a non-Thursday) is not listed.
    cases += 1
    check(failures, "AI Grants" not in str(summary["sections"]),
          f"empty section listed: {summary['sections']!r}")

    body = build_body(summary, "Thursday, September 17, 2026")

    # The body says what is really in the PDF.
    cases += 3
    check(failures, "12 sections" not in body and "15 sections" not in body,
          "body still claims a hardcoded section count")
    check(failures, "3 sections" in body and "17 stories" in body,
          f"body does not state the real counts:\n{body[:400]}")
    check(failures, "AI Hackathons" in body and "Quantum + AI" in body,
          "body does not name the real sections")

    # The stale claims are gone for good.
    cases += 1
    check(failures, "music" not in body.lower(),
          "body still mentions AI music, which the brief has never covered")

    # The date the caller passes is the date shown.
    cases += 1
    check(failures, "Thursday, September 17, 2026" in body, "body does not carry the edition date")

    # A missing analyzed_content.json degrades to a body that still sends.
    cases += 2
    check(failures, missing["total_stories"] == 0 and missing["sections"] == [],
          f"missing edition should be empty, got {missing!r}")
    fallback = build_body(missing, "Thursday, September 17, 2026")
    check(failures, "briefing" in fallback.lower() and "Thursday, September 17, 2026" in fallback,
          f"fallback body unusable:\n{fallback[:300]}")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
