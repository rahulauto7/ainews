"""Cases for summaries as long as the story needs.

Until 2026-10-02 the PDF cut every summary at 1,200 characters
(`clip_to_sentence`) and the builder flagged any summary over 1,150. Rahul's
rule since then: plain language, as long as the story needs, so he never has to
open another site to understand it. There is no upper limit, so nothing may
shorten a summary on its way to the page, and nothing may complain that one is
long. The 600-character floor and the four-sentence floor stay.

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


def main():
    failures, cases = [], 0

    # ── 1. A 3,000-character summary reaches the page whole ──────────────────
    s3k = long_summary(3000)
    _, text = render([story(s3k)])
    cases += 1
    check(failures, squash(SENTINEL) in text,
          f"a {len(s3k)}-character summary lost its last sentence on the page")

    # ── 2. A summary longer than a page runs overleaf without raising ─────────
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

    # ── 3. The builder no longer reports a long summary, only a short one ─────
    now = datetime.now(timezone.utc).isoformat()
    sections = {"global_ai_news": [
        story(s3k, title="LongStoryHere", published_at=now),
        story(long_summary(300), title="ShortStoryHere", published_at=now),
    ]}
    saved_arts, builder_helpers._ARTS = builder_helpers._ARTS, []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                builder_helpers.write_analyzed(
                    sections, out_file=os.path.join(tmp, "analyzed_content.json"))
    finally:
        builder_helpers._ARTS = saved_arts
    length_lines = [l for l in buf.getvalue().splitlines() if "summary" in l and "chars" in l]
    cases += 2
    check(failures, not [l for l in length_lines if "LongStoryHere" in l],
          f"a 3,000-character summary is still reported as too long: {length_lines!r}")
    check(failures, [l for l in length_lines if "ShortStoryHere" in l],
          f"a 300-character summary must still be reported as too short: {length_lines!r}")

    # ── 4. The sentence check names a floor, not a 4-7 range ──────────────────
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
