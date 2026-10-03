"""Cases for summary length: a full explanation, at least 1,000 characters, no ceiling.

Until 2026-10-02 the PDF cut every summary at 1,200 characters
(`clip_to_sentence`). That evening the rule became 400-800 characters to fit
15 pages, and on 2026-10-03 rahul found the five-line summaries it produced
too thin: "I want a clear understanding, in layman's terms, a news summary, no
matter how long it takes in lines." So a summary is at least 1,000 characters
and as long as the story needs; the page limit is met by carrying fewer
stories (test_page_limit.py), never by shortening explanations.
Nothing shortens a summary on its way to the page: the curator writes it, and
the page prints what was written, paragraph breaks included.

Run: python3 tools/tests/test_summary_length.py
"""

import contextlib
import io
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import builder_helpers
from check_quality import check_edition
from generate_pdf import GlobalAINewsPDF, build_section

SENTINEL = "The sentinel sentence closes this summary."
FILLER = ("The company said the new model reads whole codebases and explains its changes in "
          "plain words, which matters because engineers spend most of their day reading code. ")


def check(failures, cond, msg):
    if not cond:
        failures.append(msg)


def long_summary(chars):
    body = FILLER * (chars // len(FILLER) + 1)
    return body[:chars - len(SENTINEL)].rsplit(". ", 1)[0] + ". " + SENTINEL


def story(summary, title="A long story", **over):
    s = {"title": title, "summary": summary, "source": "The Verge",
         "url": "https://example.com/a", "relevance": 4, "tags": ["test"],
         "published_date": "2026-10-02"}
    s.update(over)
    return s


def render(stories):
    """(page count, page text with all whitespace removed) for one section."""
    from pypdf import PdfReader

    pdf = GlobalAINewsPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    build_section(pdf, "global_ai_news", stories)
    reader = PdfReader(io.BytesIO(bytes(pdf.output())))
    text = "".join(pg.extract_text() for pg in reader.pages)
    return len(reader.pages), re.sub(r"\s+", "", text)


def squash(text):
    return re.sub(r"\s+", "", text)


def builder_report(stories):
    """The problem lines write_analyzed() prints about summary length."""
    sections = {"global_ai_news": stories}
    saved_arts, builder_helpers._ARTS = builder_helpers._ARTS, []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                builder_helpers.write_analyzed(
                    sections, out_file=os.path.join(tmp, "analyzed_content.json"))
    finally:
        builder_helpers._ARTS = saved_arts
    return [l for l in buf.getvalue().splitlines() if "summary" in l and "chars" in l]


def main():
    failures, cases = [], 0

    # ── 1. The rule itself: a floor and no ceiling ───────────────────────────
    cases += 2
    check(failures, builder_helpers.SUMMARY_MIN == 1000,
          f"summary floor is {builder_helpers.SUMMARY_MIN}, expected 1000")
    check(failures, builder_helpers.SUMMARY_MAX is None,
          f"summaries must have no ceiling, found {builder_helpers.SUMMARY_MAX}")

    # ── 2. A long explanation reaches the page whole ─────────────────────────
    s2500 = long_summary(2500)
    _, text = render([story(s2500)])
    cases += 1
    check(failures, squash(SENTINEL) in text,
          f"a {len(s2500)}-character summary lost its last sentence on the page")

    # ── 3. A very long summary still prints whole, overleaf if it must ───────
    s12k = long_summary(12000)
    try:
        pages, text = render([story(s12k)])
        raised = None
    except Exception as exc:  # noqa: BLE001 - any exception is the failure
        pages, text, raised = 0, "", exc
    cases += 3
    check(failures, raised is None, f"a {len(s12k)}-character summary raised: {raised!r}")
    check(failures, pages >= 2, f"a {len(s12k)}-character summary fit on {pages} page(s)")
    check(failures, squash(SENTINEL) in text,
          "the 12,000-character summary lost its last sentence")

    # ── 4. The builder reports a summary under the floor, and nothing above ──
    now = datetime.now(timezone.utc).isoformat()
    lines = builder_report([
        story(long_summary(5000), title="LongStoryHere", published_at=now),
        story(long_summary(700), title="ShortStoryHere", published_at=now),
    ])
    cases += 2
    check(failures, not [l for l in lines if "LongStoryHere" in l],
          f"a 5,000-character summary is inside the rule: {lines!r}")
    check(failures, [l for l in lines if "ShortStoryHere" in l and "at least 1000" in l],
          f"a 700-character summary must be reported as too short: {lines!r}")

    def exact(n):
        return "a" * (n - 1) + "."

    lines = builder_report([story(exact(1000), title="AtTheFloor", published_at=now)])
    cases += 1
    check(failures, not lines, f"1,000 characters is inside the rule: {lines!r}")

    # ── 4b. Paragraphs survive the builder and reach the page ────────────────
    para = ("First paragraph says what happened.  It has two sentences.\n\n\n"
            "   Second paragraph explains why. ")
    tidy = builder_helpers.tidy_summary(para)
    cases += 2
    check(failures, tidy == ("First paragraph says what happened. It has two sentences.\n\n"
                             "Second paragraph explains why."),
          f"tidy_summary must keep one blank line between paragraphs: {tidy!r}")
    two = builder_helpers.O("T", para, "Src", "https://example.com/p", 3, [])["summary"]
    check(failures, two == tidy, f"O() must keep paragraphs: {two!r}")

    from generate_pdf import GlobalAINewsPDF as _PDF, _summary_lines
    probe = _PDF()
    probe.add_page()
    one_block = long_summary(1500)
    split_text = one_block.replace(". ", ".\n\n", 1)
    cases += 2
    check(failures, _summary_lines(probe, story(split_text)) > _summary_lines(probe, story(one_block)),
          "a paragraph break must take a line on the page")
    _, text = render([story(split_text)])
    check(failures, squash(SENTINEL) in text, "a summary in two paragraphs lost its end")

    # ── 5. The sentence check names a floor, not a range ─────────────────────
    pinned = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    three = story("OpenAI shipped a model. It reads code. It costs less.",
                  published_at=(pinned - timedelta(hours=2)).isoformat())
    found = [f for f in check_edition({"sections": {"global_ai_news": [three]}}, now=pinned)
             if f["code"] == "too_few_sentences"]
    cases += 2
    check(failures, found, "a three-sentence summary must still be flagged")
    check(failures, found and "4-7" not in found[0]["detail"],
          f"too_few_sentences still quotes an upper limit: {found and found[0]['detail']!r}")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
