"""Cases for the fifteen-page edition.

Rahul, 2026-10-02: "I am unable to read the full AI news PDF", then "make it max
15 pages". The edition had a cover page and a page per section, so sixteen
sections meant seventeen pages before a single summary ran long.

Since then: page 1 opens with a masthead and a contents list that links to each
section and names its page, sections flow on from each other, and the send is
blocked above generate_pdf.PAGE_LIMIT pages.

2026-10-03: summaries became full plain-language explanations with no ceiling,
and rahul kept the 15-page limit. So long stories run on overleaf instead of
leaving the foot of a page blank, and an edition over the limit drops stories
(builder_helpers.fit_plan) rather than shortening any explanation. All cases
here are offline.

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

# The planning figure in builder_helpers: up to three stories a section (rahul's
# card, 2026-10-04); three 1,500-character explanations a section fit 15 pages on
# a Thursday, when all seventeen sections run, with the open-roles table. Three of
# 2,000 run over, and fit_plan() drops stories (case 9).
PLAN_STORIES, PLAN_CHARS = 3, 1500
# Cut to length at a word.
TEXT = ("OpenAI released a new reasoning model on Thursday that it says solves harder maths and "
        "coding problems while costing less to run than the one before it. The company said "
        "developers can use it through the API today, and ChatGPT Plus users get it next week. "
        "Early tests by outside researchers show it beats Google's Gemini on two coding "
        "benchmarks but trails it on long documents. This matters because cheaper reasoning "
        "lets small teams build agents that check their own work before answering. Analysts "
        "expect rivals to cut prices again within a month. ") * 12
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
    # find_roles.table_rows() shape: ten rows, the most the builder asks for.
    roles = {"as_of": "2026-10-02", "best_for": [
        {"use_case": f"Company {i}", "model": "Forward Deployed Engineer, Enterprise",
         "maker": "Remote, worldwide",
         "why": ("Sponsors visas. " if i % 2 else "") + "Posted 2 Oct on Greenhouse.",
         "url": f"https://example.com/jobs/{i}"}
        for i in range(10)]}
    return {"sections": sections,
            "section_extras": {"open_model_landscape": table, "closed_model_landscape": table,
                               "fde_careers": roles}}


def read(pdf):
    from pypdf import PdfReader
    return PdfReader(io.BytesIO(bytes(pdf.output())))


def squash(text):
    return re.sub(r"\s+", "", text).lower()


def main():
    failures, cases = [], 0

    cases += 1
    check(failures, PAGE_LIMIT == 15, f"PAGE_LIMIT is {PAGE_LIMIT}; rahul asked for 15 pages max")

    # ── 1. A full Thursday edition at the planning figure fits ───────────────
    # Seventeen sections (quantum runs on Thursdays), three 1,500-character
    # explanations each, both model tables and the open-roles table.
    full = edition(PLAN_STORIES, PLAN_CHARS)
    reader = read(render_edition(full))
    pages = [pg.extract_text() for pg in reader.pages]
    cases += 1
    check(failures, len(pages) <= PAGE_LIMIT,
          f"a {len(SECTION_ORDER)}-section edition of {PLAN_STORIES} {PLAN_CHARS:,}-character "
          f"stories ran to {len(pages)} pages")

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

    numbers = re.findall(rf"\({PLAN_STORIES}\)\s*p(\d+)", page1)
    cases += 1
    check(failures, len(numbers) == len(SECTION_ORDER) and numbers == sorted(numbers, key=int),
          f"contents must name each section's page, in order: {numbers}")

    # ── 4. A section header is never left alone at the foot of a page ────────
    # The page the contents names is the header's page; the section's first
    # block - its table where it has one, else its first story - must be there.
    orphans = []
    for key, num in zip(SECTION_ORDER, numbers):
        if key == "fde_careers":
            first = "openroles"
        elif key in full["section_extras"]:
            first = "best" + ("open" if key.startswith("open") else "closed") + "model"
        else:
            first = squash(full["sections"][key][0]["title"])[:30]
        if first not in squash(pages[int(num) - 1]):
            orphans.append(key)
    cases += 1
    check(failures, not orphans, f"headers parted from their first block: {orphans}")

    # A table section whose header and table only just fit keeps them together:
    # the header's test and the table's own page break measure the same bottom.
    from generate_pdf import GlobalAINewsPDF, PAGE_BOTTOM, SECTION_HEAD_H, _best_for_layout, build_section
    table = full["section_extras"]["open_model_landscape"]
    probe = GlobalAINewsPDF()
    probe.add_page()
    box_h = _best_for_layout(probe, table)[2]
    split = []
    for slack in (0.5, 1.5, 2.5):
        pdf = GlobalAINewsPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.add_page()
        pdf.set_y(PAGE_BOTTOM - SECTION_HEAD_H - box_h - 2 - slack)  # build_section adds 2
        head_page = build_section(pdf, "open_model_landscape", [], table)
        texts = [pg.extract_text() for pg in read(pdf).pages]
        if "BEST OPEN" not in texts[head_page - 1]:
            split.append(slack)
    cases += 1
    check(failures, not split, f"header and table parted at {split}mm of slack")

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

    # One layout pass counts the pages the two-pass render prints.
    from generate_pdf import page_count
    cases += 1
    check(failures, page_count(full) == len(pages),
          f"page_count() says {page_count(full)}, the render has {len(pages)} pages")

    # ── 7. A normal (non-Thursday) day has room to spare ─────────────────────
    cases += 1
    weekday = len(read(render_edition(edition(PLAN_STORIES, PLAN_CHARS, quantum=False))).pages)
    check(failures, weekday < PAGE_LIMIT,
          f"{len(SECTION_ORDER) - 1} sections at the planning figure took {weekday} pages, "
          "no room to spare")

    # ── 8. Over the limit: reported by the builder, blocked at send ──────────
    over = edition(8, 1000)
    cases += 1
    over_pages = len(read(render_edition(over)).pages)
    check(failures, over_pages > PAGE_LIMIT,
          f"eight 1,000-character stories a section should overflow, took {over_pages} pages")

    saved, builder_helpers._ARTS = builder_helpers._ARTS, []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                builder_helpers.write_analyzed(
                    over["sections"], best_for=over["section_extras"]["open_model_landscape"],
                    closed_best_for=over["section_extras"]["closed_model_landscape"],
                    out_file=os.path.join(tmp, "analyzed_content.json"))
    finally:
        builder_helpers._ARTS = saved
    printed = buf.getvalue()
    cases += 2
    check(failures, f"{over_pages} pages" in printed.splitlines()[0],
          f"the builder's first line must give the page count: {printed.splitlines()[0]!r}")
    check(failures, f"limit {PAGE_LIMIT}" in printed,
          f"the builder must flag a PDF over the limit, printed:\n{printed[:400]}")
    cases += 1
    check(failures, "to fit, drop:" in printed,
          f"the builder must name the stories to drop, printed:\n{printed[:600]}")

    # ── 9. The fit plan drops stories, lowest relevance first, never below a ──
    # section's floor (story_rule()) or its last story.
    plan_ed = edition(4, 2000)
    for key, stories in plan_ed["sections"].items():
        stories[-1]["relevance"] = 2  # the weakest story in every section
    drops = builder_helpers.fit_plan(plan_ed, PAGE_LIMIT)
    for key, story in drops:
        plan_ed["sections"][key].remove(story)
    left = {k: len(v) for k, v in plan_ed["sections"].items()}
    cases += 4
    check(failures, drops, "four 2,000-character stories a section must need a fit plan")
    check(failures, render_edition(plan_ed).page_no() <= PAGE_LIMIT,
          f"after the fit plan's {len(drops)} drops the edition still runs over")
    check(failures, all(n >= max(builder_helpers.story_rule(k)[0], 1) for k, n in left.items()),
          f"the fit plan took a section below its floor: {left}")
    weak = len(plan_ed["sections"])  # one relevance-2 story per section
    check(failures, all(s.get("relevance") == 2 for _, s in drops[:weak])
          and all(s.get("relevance") != 2 for _, s in drops[weak:]),
          "the fit plan must drop the lowest-relevance stories first")
    cases += 1
    check(failures, builder_helpers.fit_plan(edition(2, 1000), PAGE_LIMIT) == [],
          "an edition that fits needs no drops")

    # ── 10. Long stories run on overleaf; short ones move whole ──────────────
    from generate_pdf import (MIN_LINES_AFTER_BREAK, MIN_LINES_BEFORE_BREAK, PAGE_BREAK_Y,
                              STORY_HEAD_H, SUMMARY_LH, _summary_lines)
    long_story = dict(full["sections"]["global_ai_news"][0],
                      title="Runs on overleaf, a long explained story", summary=summary(2400))
    short_story = dict(long_story, title="Moves whole, a short story", summary=summary(300))

    def at(y, story):
        pdf = GlobalAINewsPDF()
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.add_page()
        pdf.set_y(y)
        build_section(pdf, "global_ai_news", [dict(full["sections"]["global_ai_news"][1],
                                                   summary=summary(120)), story])
        return [squash(pg.extract_text()) for pg in read(pdf).pages]

    probe = GlobalAINewsPDF()
    probe.add_page()
    first_h = STORY_HEAD_H + _summary_lines(probe, dict(long_story, summary=summary(120))) * SUMMARY_LH + 2
    # Start the long story with room for its title and five lines.
    y = PAGE_BREAK_Y - first_h - SECTION_HEAD_H - 2 - STORY_HEAD_H - 5 * SUMMARY_LH - 0.5
    texts = at(y, long_story)
    tail = squash(long_story["summary"])[-40:]
    head = squash(long_story["title"])[:30]
    cases += 2
    check(failures, head in texts[1] and tail in texts[2],
          "a long story with room for five lines must start on the page and finish overleaf")
    check(failures, len(texts) == 3, f"the run-on story took {len(texts)} pages, expected 3")

    # With room for only two lines, it moves overleaf whole instead.
    y = PAGE_BREAK_Y - first_h - SECTION_HEAD_H - 2 - STORY_HEAD_H - 2 * SUMMARY_LH - 0.5
    texts = at(y, long_story)
    cases += 1
    check(failures, head not in texts[1] and head in texts[2],
          f"with room for fewer than {MIN_LINES_BEFORE_BREAK} lines the story must move overleaf")

    # A story too short to split never splits.
    texts = at(y, short_story)
    cases += 1
    check(failures, squash(short_story["title"])[:30] in texts[2]
          and squash(short_story["summary"])[-30:] in texts[2],
          f"a story under {MIN_LINES_BEFORE_BREAK + MIN_LINES_AFTER_BREAK} lines must move whole")

    cases += 3
    check(failures, page_problem(PAGE_LIMIT) is None, "a PDF at the limit must not block")
    check(failures, page_problem(6) is None, "a 6-page PDF must not block")
    blocked = page_problem(PAGE_LIMIT + 1)
    check(failures, blocked and str(PAGE_LIMIT + 1) in blocked,
          f"a PDF over the limit must block the send: {blocked!r}")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
