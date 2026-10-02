"""Cases for the six-page edition.

Rahul, 2026-10-02: "I am unable to read the full AI news PDF, so make it less
pages, like 5-6 pages, so I can cover every section, understand every section,
and read every section." The edition had a cover page and a page per section,
so sixteen sections meant seventeen pages before a single summary ran long.

Since then: page 1 opens with a masthead and a contents list that links to each
section and names its page, sections flow on from each other, and the send is
blocked above generate_pdf.PAGE_LIMIT pages. All cases here are offline.

Run: python3 tools/tests/test_page_limit.py
"""

import contextlib
import io
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import builder_helpers
from generate_pdf import PAGE_LIMIT, SECTION_CONFIG, SECTION_ORDER, render_edition
from verify_edition import page_problem

# Cut to length at a word, so a full edition of summary(SUMMARY_MAX) is the worst
# case the builder's rule accepts.
TEXT = ("OpenAI released a new reasoning model on Thursday that it says solves harder maths and "
        "coding problems while costing less to run than the one before it. The company said "
        "developers can use it through the API today, and ChatGPT Plus users get it next week. "
        "Early tests by outside researchers show it beats Google's Gemini on two coding "
        "benchmarks but trails it on long documents. This matters because cheaper reasoning "
        "lets small teams build agents that check their own work before answering. Analysts "
        "expect rivals to cut prices again within a month. ") * 3
WHY = ("Leads the LMArena coding board this week and costs a third of the next best; "
       "the licence allows commercial use.")


def check(failures, cond, msg):
    if not cond:
        failures.append(msg)


def summary(chars):
    return TEXT[:chars - 1].rsplit(" ", 1)[0] + "."


def edition(per_section, chars, quantum=True):
    sections = {}
    for n, key in enumerate(SECTION_ORDER):
        if key == "quantum_ai_research" and not quantum:
            continue
        sections[key] = [{
            "title": f"Story {n}-{i}: Anthropic launches Claude agent tools for enterprise teams",
            "summary": summary(chars), "source": "TechCrunch",
            "url": f"https://example.com/{key}/{i}", "relevance": 4,
            "published_date": "2026-10-02", "deadline": "20 Oct 2026",
            "apply_url": "https://lablab.ai/event/x", "prize": "$50,000",
        } for i in range(per_section)]
    table = {"as_of": "2026-10-02", "best_for": [
        {"use_case": u, "model": "Qwen3.8-Max", "maker": "Alibaba", "licence": "Apache 2.0",
         "why": WHY}
        for u in ("Coding", "Reasoning and maths", "Long documents", "Everyday chat",
                  "Small and local")]}
    return {"sections": sections,
            "section_extras": {"open_model_landscape": table, "closed_model_landscape": table}}


def read(pdf):
    from pypdf import PdfReader
    return PdfReader(io.BytesIO(bytes(pdf.output())))


def squash(text):
    return re.sub(r"\s+", "", text).lower()


def main():
    failures, cases = [], 0

    cases += 1
    check(failures, PAGE_LIMIT == 6, f"PAGE_LIMIT is {PAGE_LIMIT}; rahul asked for 5-6 pages")

    # ── 1. A full Thursday edition at the builder's limits fits ──────────────
    # Sixteen sections (quantum runs on Thursdays), two stories each at the
    # summary ceiling, and both model tables: the most the rules allow.
    full = edition(builder_helpers.STORIES_PER_SECTION[1], builder_helpers.SUMMARY_MAX)
    reader = read(render_edition(full))
    pages = [pg.extract_text() for pg in reader.pages]
    cases += 1
    check(failures, len(pages) <= PAGE_LIMIT,
          f"a 16-section edition at the builder's limits ran to {len(pages)} pages")

    # ── 2. Every story is in it ──────────────────────────────────────────────
    whole = squash("".join(pages))
    lost = [s["title"] for v in full["sections"].values() for s in v
            if squash(s["title"])[:30] not in whole]
    cases += 1
    check(failures, not lost, f"{len(lost)} stories missing, e.g. {lost[:1]}")

    # ── 3. The contents list: every section, with its page ───────────────────
    page1 = pages[0]
    listed = [k for k in SECTION_ORDER if SECTION_CONFIG[k]["label"] in page1]
    cases += 1
    check(failures, len(listed) == len(SECTION_ORDER),
          f"contents lists {len(listed)} of {len(SECTION_ORDER)} sections")

    numbers = re.findall(r"\(2\)\s*p(\d)", page1)
    cases += 1
    check(failures, len(numbers) == len(SECTION_ORDER) and numbers == sorted(numbers),
          f"contents must name each section's page, in order: {numbers}")

    # ── 4. A section header is never left alone at the foot of a page ────────
    # The page the contents names is the header's page; the section's first
    # block - its table where it has one, else its first story - must be there.
    orphans = []
    for key, num in zip(SECTION_ORDER, numbers):
        if key in full["section_extras"]:
            first = "best" + ("open" if key.startswith("open") else "closed") + "model"
        else:
            first = squash(full["sections"][key][0]["title"])[:30]
        if first not in squash(pages[int(num) - 1]):
            orphans.append(key)
    cases += 1
    check(failures, not orphans, f"headers parted from their first block: {orphans}")

    # ── 5. Each contents entry links to the page it names ────────────────────
    index = {pg.indirect_reference.idnum: n + 1 for n, pg in enumerate(reader.pages)}
    dests = []
    for annot in reader.pages[0].get("/Annots") or []:
        a = annot.get_object()
        if "/Dest" in a:
            dests.append(index.get(a["/Dest"][0].idnum))
    # Two links per entry (the label and the page number), in contents order.
    targets = dests[::2]
    cases += 1
    check(failures, targets == [int(n) for n in numbers],
          f"contents links land on {targets}, the list says {numbers}")

    # ── 6. Titles stay clickable now the URL line is gone ────────────────────
    uris = {a.get_object()["/A"]["/URI"] for pg in reader.pages for a in pg.get("/Annots") or []
            if "/A" in a.get_object() and "/URI" in a.get_object()["/A"]}
    want = {s["url"] for v in full["sections"].values() for s in v}
    cases += 2
    check(failures, want <= uris, f"{len(want - uris)} story titles lost their link")
    check(failures, "example.com/" not in whole,
          "a story URL is printed; the title carries the link")

    # ── 7. A normal (non-Thursday) day has room to spare ─────────────────────
    cases += 1
    weekday = len(read(render_edition(edition(2, builder_helpers.SUMMARY_MAX,
                                              quantum=False))).pages)
    check(failures, weekday <= 5, f"15 sections at the summary ceiling took {weekday} pages")

    # ── 8. Over the limit: reported by the builder, blocked at send ──────────
    over = edition(3, 800)
    cases += 1
    over_pages = len(read(render_edition(over)).pages)
    check(failures, over_pages > PAGE_LIMIT,
          f"three 800-character stories a section should overflow, took {over_pages} pages")

    saved, builder_helpers._ARTS = builder_helpers._ARTS, []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                builder_helpers.write_analyzed(
                    over["sections"], best_for=over["section_extras"]["open_model_landscape"],
                    out_file=os.path.join(tmp, "analyzed_content.json"))
    finally:
        builder_helpers._ARTS = saved
    printed = buf.getvalue()
    cases += 2
    check(failures, f"{over_pages} pages" in printed.splitlines()[0],
          f"the builder's first line must give the page count: {printed.splitlines()[0]!r}")
    check(failures, f"limit {PAGE_LIMIT}" in printed,
          f"the builder must flag a PDF over the limit, printed:\n{printed[:400]}")

    cases += 3
    check(failures, page_problem(PAGE_LIMIT) is None, "a PDF at the limit must not block")
    check(failures, page_problem(5) is None, "a 5-page PDF must not block")
    blocked = page_problem(PAGE_LIMIT + 1)
    check(failures, blocked and str(PAGE_LIMIT + 1) in blocked,
          f"a PDF over the limit must block the send: {blocked!r}")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
