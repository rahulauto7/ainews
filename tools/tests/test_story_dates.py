"""Cases for the per-story publish date reaching the PDF.

Every edition from 2026-04 to 2026-09-17 shipped with a blank date on every
story line: generate_pdf._format_published() reads `published_date`, but S()
built its story dict without ever copying that field off the source article,
so all 64 stories came out as "Source: X  |  ..." with nothing between them.
The renderer was never the bug - the data was empty.

The two opportunity sections are deliberately exempt. _fit_meta_line() protects
parts[0] and parts[1] and drops from the tail, so a publish date inserted at
position 1 pushes "Due:" and "Apply:" - the only two fields a reader acts on -
off the end of the line.

Run: python3 tools/tests/test_story_dates.py
"""

import contextlib
import io
import os
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import builder_helpers
from builder_helpers import O, S
from generate_pdf import _format_published, _meta_parts

# Two shapes the scraper produces: a normal feed item carries both fields, and
# a handful of feeds emit only the full ISO timestamp with no date field.
ARTICLES = [
    {"title": "Anthropic ships Claude Code hooks", "url": "https://example.com/a",
     "source": "The Verge", "summary": "...", "category": "general",
     "published": "2026-09-16T23:53:50+00:00", "published_date": "2026-09-16"},
    {"title": "Qwen 3 weights land on Hugging Face", "url": "https://example.com/b",
     "source": "VentureBeat", "summary": "...", "category": "open_model",
     "published": "2026-09-15T06:00:00+00:00"},
]

# 507 characters: inside the builder's 400-600 rule, so only the dates get flagged.
SUMMARY = "A plain-language summary of the story. " * 13


def check(failures, ok, message):
    if not ok:
        failures.append(message)


def main():
    failures = []
    cases = 0

    builder_helpers._ARTS = ARTICLES  # offline: no rss_articles.json read

    # S() carries the source article's date onto the story.
    story = S(0, SUMMARY, 5, ["anthropic"])
    cases += 1
    check(failures, story.get("published_date") == "2026-09-16",
          f"S() dropped the date: published_date={story.get('published_date')!r}")

    # A feed that emits only the ISO timestamp still yields a usable date.
    story_iso = S(1, SUMMARY, 4, ["open-model"])
    cases += 1
    check(failures, story_iso.get("published_date") == "2026-09-15",
          f"S() did not derive a date from `published`: {story_iso.get('published_date')!r}")

    # An explicit override still wins - a Google News proxy item is dated by the
    # publisher page, not by the day Google resurfaced it.
    story_override = S(0, SUMMARY, 5, ["anthropic"], published_date="2026-09-10")
    cases += 1
    check(failures, story_override.get("published_date") == "2026-09-10",
          f"S() ignored an explicit published_date: {story_override.get('published_date')!r}")

    # O() is for opportunities verified on the organiser's page - there is no
    # feed article and so no publish date, and a blank beats an invention.
    # The deadline sits a month out from whenever the test runs: the hackathon
    # section's 7-day build rule would otherwise flag it once the date nears.
    opp = O("Y Combinator W27", SUMMARY, "Y Combinator", "https://ycombinator.com/apply",
            5, ["accelerator"], deadline=f"{date.today() + timedelta(days=30):%d %b %Y}")
    cases += 1
    check(failures, "published_date" not in opp,
          f"O() invented a date: {opp.get('published_date')!r}")

    # ...but accepts one when the organiser's page carries a dated announcement.
    opp_dated = O("IAPS Fellowship", SUMMARY, "IAPS", "https://iaps.ai/fellowship",
                  5, ["fellowship"], published_date="2026-09-12")
    cases += 1
    check(failures, opp_dated.get("published_date") == "2026-09-12",
          f"O() rejected an explicit date: {opp_dated.get('published_date')!r}")

    # _format_published renders both shapes without a leading zero on the day.
    cases += 2
    check(failures, _format_published({"published_date": "2026-09-06"}) == "Sep 6, 2026",
          f"_format_published: {_format_published({'published_date': '2026-09-06'})!r}")
    check(failures, _format_published({"published": "2026-09-16T23:53:50+00:00"}) == "Sep 16, 2026",
          f"_format_published ISO: {_format_published({'published': '2026-09-16T23:53:50+00:00'})!r}")

    # A normal section puts the date straight after the source.
    parts = _meta_parts("anthropic_claude_news", story)
    cases += 2
    check(failures, parts[:1] == ["Source: The Verge"], f"meta parts={parts!r}")
    check(failures, parts[1:2] == ["Sep 16, 2026"],
          f"date must follow the source on a news line, got parts={parts!r}")

    # The two opportunity sections stay date-free so Due/Apply survive the fit.
    for key in ("ai_hackathons", "product_showcase_opportunities"):
        hack = dict(story, published_date="2026-09-16", deadline="23 Oct 2026",
                    apply_url="https://devpost.com/x", opportunity_type="Online hackathon")
        parts = _meta_parts(key, hack)
        cases += 1
        check(failures, "Sep 16, 2026" not in parts,
              f"{key}: publish date must not displace Due/Apply, got {parts!r}")

    # A story with no date at all renders without an empty separator.
    parts = _meta_parts("global_ai_news", {"source": "Reuters", "title": "t"})
    cases += 1
    check(failures, parts == ["Source: Reuters"], f"undated story: {parts!r}")

    # write_analyzed() reports an undated news story, so a silent regression to
    # the 2026-04..09-17 behaviour cannot reach the PDF unnoticed. Opportunity
    # sections are exempt - O() items legitimately carry no publish date.
    dated = dict(story, title="Dated", summary=SUMMARY, url="https://example.com/a")
    undated = {k: v for k, v in dated.items() if k != "published_date"}
    undated["title"] = "Undated"
    opp_story = dict(opp, summary=SUMMARY)
    sections = {
        "global_ai_news": [dated, undated],
        "ai_hackathons": [opp_story, dict(opp_story, title="O2")],
    }
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "analyzed_content.json")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            builder_helpers.write_analyzed(sections, out_file=out)
        printed = buf.getvalue()
    cases += 2
    check(failures, "Undated" in printed and "no date" in printed.lower(),
          f"write_analyzed must flag the undated news story, printed:\n{printed}")
    check(failures, "O2" not in printed,
          f"write_analyzed must not flag undated opportunities, printed:\n{printed}")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
