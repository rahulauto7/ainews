"""Cases for the closed-model section and its standing benchmark table.

Section 9, `closed_model_landscape`, carries the same shape as the open-model
section that precedes it: 3-6 news stories plus one standing "best model at
what" table in `section_extras`. Everything that was written once for the open
table - the renderer, the carry-forward, the staleness warning, the rendered-text
comparison - had the key `open_model_landscape` hardcoded, so the cases below
pin the generalisation: two tables, each with its own heading, carried forward
and checked independently.

`access` replaces `licence` for a closed model: what the reader cannot infer
from the name is what it costs and where to get it, not the licence.

Run: python3 tools/tests/test_closed_model_table.py
"""

import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import builder_helpers
import web_text
from check_quality import check_edition
from generate_pdf import SECTION_CONFIG, SECTION_ORDER, _model_line, _table_heading
from verify_edition import source_text

OPEN_KEY = "open_model_landscape"
CLOSED_KEY = "closed_model_landscape"
NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)

OPEN_ROW = {"use_case": "Coding", "model": "Qwen3.8-Max", "maker": "Alibaba",
            "licence": "MIT", "why": "New today: tops Code Arena at 1,691."}
CLOSED_ROW = {"use_case": "Coding", "model": "GPT-5.4", "maker": "OpenAI",
              "access": "API, $1.25/$10 per M tokens",
              "why": "New today: 78.1 on SWE-bench Verified, per OpenAI's release note."}


def check(failures, cond, msg):
    if not cond:
        failures.append(msg)


def edition(sections, extras=None):
    return {"sections": sections, "section_extras": extras or {},
            "section_labels": {}, "analyzed_at": "2026-09-17T00:00:00+00:00"}


def story(**over):
    s = {"title": "OpenAI ships GPT-5.4", "summary": "x. " * 40, "source": "The Verge",
         "url": "https://example.com/a", "relevance": 5, "tags": ["openai"],
         "published_date": "2026-09-16"}
    s.update(over)
    return s


def render_best_for(rows, heading="BEST CLOSED MODEL RIGHT NOW"):
    """Draw one standing table on a real page and return its extracted text, squashed.

    Squashed because a wrapped label arrives from the extractor split across lines
    ("Everyday high-volume\nwork"), and what matters is that the words survived in
    order and did not run into the model column.
    """
    from fpdf import FPDF
    from pypdf import PdfReader

    from generate_pdf import build_best_for_box

    pdf = FPDF()
    pdf.add_page()
    build_best_for_box(pdf, 20, (60, 60, 160),
                       {"as_of": "2026-09-23", "best_for": rows}, heading=heading)
    reader = PdfReader(io.BytesIO(bytes(pdf.output())))
    return " ".join("\n".join(pg.extract_text() for pg in reader.pages).split())


def main():
    failures, cases = [], 0

    # ── The section itself ────────────────────────────────────────────────────
    cases += 1
    check(failures, CLOSED_KEY in SECTION_CONFIG, f"{CLOSED_KEY} missing from SECTION_CONFIG")

    cases += 1
    check(failures, SECTION_ORDER.index(CLOSED_KEY) == SECTION_ORDER.index(OPEN_KEY) + 1,
          "closed section must render directly after the open one, so the two tables read together")

    cases += 1
    check(failures, len(SECTION_ORDER) == len(set(SECTION_ORDER)) == len(SECTION_CONFIG),
          "SECTION_ORDER and SECTION_CONFIG must hold the same keys, once each")

    cases += 1
    colours = [c["color"] for c in SECTION_CONFIG.values()]
    check(failures, len(colours) == len(set(colours)),
          "every section needs its own colour; the closed section reuses one")

    # ── Headings: one renderer, a heading per section ─────────────────────────
    cases += 2
    check(failures, "OPEN" in _table_heading(OPEN_KEY, {}),
          f"open heading lost its wording: {_table_heading(OPEN_KEY, {})!r}")
    check(failures, "CLOSED" in _table_heading(CLOSED_KEY, {}),
          f"closed heading lost its wording: {_table_heading(CLOSED_KEY, {})!r}")

    cases += 1
    check(failures, "2026-09-11" in _table_heading(CLOSED_KEY, {"as_of": "2026-09-11"}),
          "as_of must print in the heading, so a stale table is visible rather than silent")

    # ── A row's access line stands in for a licence ───────────────────────────
    cases += 3
    check(failures, _model_line(CLOSED_ROW) == "GPT-5.4 (OpenAI, API, $1.25/$10 per M tokens)",
          f"access not rendered: {_model_line(CLOSED_ROW)!r}")
    check(failures, _model_line(OPEN_ROW) == "Qwen3.8-Max (Alibaba, MIT)",
          f"licence rendering changed: {_model_line(OPEN_ROW)!r}")
    check(failures, _model_line({"model": "M"}) == "M",
          "a row with neither licence nor access must still render its model")

    # ── Carry-forward, per table ──────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        saved = web_text.TMP_DIR
        web_text.TMP_DIR = tmp
        try:
            prior = {"sections": {}, "section_extras": {
                OPEN_KEY: {"as_of": "2026-09-11", "best_for": [dict(OPEN_ROW)]},
                CLOSED_KEY: {"as_of": "2026-09-12", "best_for": [dict(CLOSED_ROW)]},
            }}
            with open(os.path.join(tmp, "analyzed_content_2026-09-13.bak.json"), "w") as f:
                json.dump(prior, f)
            closed = builder_helpers.carry_forward_best_for("2026-09-15", section_key=CLOSED_KEY)
            open_block = builder_helpers.carry_forward_best_for("2026-09-15")
        finally:
            web_text.TMP_DIR = saved

    cases += 4
    check(failures, closed and closed["best_for"][0]["model"] == "GPT-5.4",
          f"carry_forward_best_for(section_key=) returned the wrong table: {closed!r}")
    check(failures, closed and closed["best_for"][0]["why"].startswith("Carried forward:"),
          f"closed row not relabelled: {closed and closed['best_for'][0]['why']!r}")
    check(failures, closed and closed["as_of"] == "2026-09-12",
          "as_of must not change on a carry-forward")
    check(failures, open_block and open_block["best_for"][0]["model"] == "Qwen3.8-Max",
          f"the default key must still be the open table: {open_block!r}")

    # ── write_analyzed carries both blocks ────────────────────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        saved_arts, builder_helpers._ARTS = builder_helpers._ARTS, []
        out_file = os.path.join(tmp, "analyzed_content.json")
        try:
            with redirect_stdout(io.StringIO()):
                out = builder_helpers.write_analyzed(
                    {CLOSED_KEY: [story(), story(), story()]},
                    best_for={"as_of": "2026-09-13", "best_for": [dict(OPEN_ROW)]},
                    closed_best_for={"as_of": "2026-09-13", "best_for": [dict(CLOSED_ROW)]},
                    out_file=out_file)
        finally:
            builder_helpers._ARTS = saved_arts

    cases += 3
    check(failures, set(out["section_extras"]) == {OPEN_KEY, CLOSED_KEY},
          f"both tables must reach section_extras: {sorted(out['section_extras'])}")
    check(failures, out["section_labels"].get(CLOSED_KEY),
          "the closed section needs a label, or the cover page and email body cannot name it")
    check(failures, out["sections"][CLOSED_KEY][0]["title"] == "OpenAI ships GPT-5.4",
          "stories must survive write_analyzed unchanged")

    # ── Staleness warns on either table, naming the one that aged ─────────────
    stale = edition({"global_ai_news": [story()]},
                    {CLOSED_KEY: {"as_of": "2026-08-20", "best_for": [dict(CLOSED_ROW)]}})
    found = check_edition(stale, today="2026-09-17", now=NOW)
    stale_findings = [f for f in found if f["code"] == "stale_best_for"]
    cases += 2
    check(failures, stale_findings, f"stale closed table not caught (28 days): {found!r}")
    check(failures, stale_findings and stale_findings[0]["section"] == CLOSED_KEY,
          f"finding must name the table that aged: {stale_findings!r}")

    fresh = edition({"global_ai_news": [story()]}, {
        OPEN_KEY: {"as_of": "2026-09-14", "best_for": [dict(OPEN_ROW)]},
        CLOSED_KEY: {"as_of": "2026-09-14", "best_for": [dict(CLOSED_ROW)]},
    })
    cases += 1
    check(failures, not [f for f in check_edition(fresh, today="2026-09-17", now=NOW)
                         if f["code"] == "stale_best_for"],
          "staleness fired on two tables three days old")

    # ── The rendered-page comparison must see the closed table's text ─────────
    src = source_text(fresh)
    cases += 2
    check(failures, "GPT-5.4" in src and "API, $1.25/$10 per M tokens" in src,
          "closed table text is missing from source_text, so nothing checks it against the PDF")
    check(failures, "Qwen3.8-Max" in src, "open table text dropped out of source_text")

    # ── A long use_case must wrap inside its column, not overrun the model line ──
    # The 2026-09-23 edition shipped "Everyday high-volume woGrPkT-6 Luna". The
    # label was drawn with a [:26] *character* slice into a 34mm column, so the two
    # widest closed-table labels overlapped the model text beside them and
    # "Balanced cost and capability" was additionally cut mid-word. A character
    # count says nothing about width - the same lesson as _fit_title(). The open
    # table never hit it because its five fixed use cases are all under 26mm.
    wide = render_best_for([
        {"use_case": "Everyday high-volume work", "model": "GPT-6 Luna", "maker": "OpenAI",
         "access": "OpenAI API, $0.10/$0.50 per M tokens",
         "why": "New today: priced at ten cents per million input tokens."},
        {"use_case": "Balanced cost and capability", "model": "GPT-6 Sol", "maker": "OpenAI",
         "access": "OpenAI API, $2/$10 per M tokens",
         "why": "New today: half the token price of GPT-5.6 Sol."},
    ])
    # Asserted with the model line attached: the label surviving on its own is not
    # enough, because an overlapping label still extracts as "...workGPT-6 Luna".
    cases += 2
    check(failures,
          "Everyday high-volume work GPT-6 Luna (OpenAI, OpenAI API, "
          "$0.10/$0.50 per M tokens)" in wide,
          "a 25-character use_case ran into the model line beside it")
    check(failures,
          "Balanced cost and capability GPT-6 Sol (OpenAI, OpenAI API, "
          "$2/$10 per M tokens)" in wide,
          "'Balanced cost and capability' was cut mid-word and ran into the model line")

    # Short labels must still render on one line, unchanged.
    narrow = render_best_for([dict(OPEN_ROW)], heading="BEST OPEN MODEL RIGHT NOW")
    cases += 1
    check(failures, "Coding Qwen3.8-Max (Alibaba, MIT)" in narrow,
          "a short use_case stopped sitting on one line beside its model")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
