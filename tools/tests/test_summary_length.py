"""Cases for summary length: 400-550 characters, printed whole.

Until 2026-10-02 the PDF cut every summary at 1,200 characters
(`clip_to_sentence`). That morning the rule became "as long as the story
needs", and the same evening rahul found the result too long to read: "make it
less pages, like 5-6 pages, so I can cover every section". So summaries are
400-550 characters, the size that fits two stories a section in six pages
(see test_page_limit.py), and the builder reports any outside that range.
Nothing shortens a summary on its way to the page: the curator writes it to
length, and the page prints what was written.

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

    # ── 1. The range itself ──────────────────────────────────────────────────
    cases += 1
    check(failures, (builder_helpers.SUMMARY_MIN, builder_helpers.SUMMARY_MAX) == (400, 550),
          f"summary rule is {builder_helpers.SUMMARY_MIN}-{builder_helpers.SUMMARY_MAX}, "
          "expected 400-550")

    # ── 2. A summary at the ceiling reaches the page whole ───────────────────
    s550 = long_summary(550)
    _, text = render([story(s550)])
    cases += 1
    check(failures, squash(SENTINEL) in text,
          f"a {len(s550)}-character summary lost its last sentence on the page")

    # ── 3. An over-long summary still prints whole, overleaf if it must ──────
    # The builder reports it; the page never clips it, so nothing the curator
    # wrote goes missing silently.
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

    # ── 4. The builder reports a summary outside 400-550, both ways ──────────
    now = datetime.now(timezone.utc).isoformat()
    lines = builder_report([
        story(long_summary(900), title="LongStoryHere", published_at=now),
        story(long_summary(300), title="ShortStoryHere", published_at=now),
    ])
    cases += 2
    check(failures, [l for l in lines if "LongStoryHere" in l and "400-550" in l],
          f"a 900-character summary must be reported as too long: {lines!r}")
    check(failures, [l for l in lines if "ShortStoryHere" in l],
          f"a 300-character summary must be reported as too short: {lines!r}")

    def exact(n):
        return "a" * (n - 1) + "."

    lines = builder_report([
        story(exact(400), title="AtTheFloor", published_at=now),
        story(exact(550), title="AtTheCeiling", published_at=now),
    ])
    cases += 1
    check(failures, not lines, f"400 and 550 characters are inside the rule: {lines!r}")

    # ── 5. The sentence check names a floor, not a 4-7 range ──────────────────
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
