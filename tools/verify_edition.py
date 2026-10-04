"""Every pre-send check, plus the backup and the send, in one call.

The 2026-09-17 run spent turns 76-110 on this - 35 model turns at 220-244k
context, close to 8M tokens - running the tests, rendering the PDF, extracting
its text, eyeballing question marks, taking the backup and reading the mail tool,
one command per turn. None of it needs a model in the loop.

Order, and what stops the run:

  1. test suite            tools/tests/test_*.py      FAIL -> stop
  2. generate the PDF      generate_pdf.py            FAIL -> stop
  3. rendered-text checks  stray '?', cut summaries,  FAIL -> stop
                           over the page limit
  4. quality review        check_quality.py           ERROR -> stop, WARN -> print
     (includes the freshness rule - 24h, quantum 7d - measured at send)
  5. backup                analyzed_content_<DATE>.bak.json
  6. send                  send_email.py              only with --send

Step 5 runs as soon as the PDF is verified, not at the start of the next run.
Taking the backup late is what let the 2026-09-15 edition vanish untraced.

Usage:
  python3 tools/verify_edition.py                 # verify and back up, no mail
  python3 tools/verify_edition.py --send          # ...and mail it
  python3 tools/verify_edition.py --skip-pdf      # PDF already rendered this run
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import web_text
from check_quality import _is_truncated, check_edition, freshness_lines

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
ANALYZED = os.path.join(web_text.TMP_DIR, "analyzed_content.json")


def _squash(text):
    """Comparable form of a string on both sides of the render.

    Two things move between the JSON and the extracted page: sanitize_text()
    folds characters outside latin-1 (a curly apostrophe becomes a straight one),
    and multi_cell() wraps a title across lines, so the extracted text carries
    breaks the source never had. Dropping whitespace and case handles both.
    """
    from generate_pdf import sanitize_text
    return re.sub(r"\s+", "", sanitize_text(text or "")).lower()


def source_text(data):
    """Every string the PDF renders, so the rendered page can be compared to it.

    The story URL is left out: since 2026-10-02 it is the title's link target and
    is not printed, and a query string's '?' counted here would hide a stray one.
    """
    parts = []
    for stories in (data.get("sections") or {}).values():
        for s in stories or []:
            parts += [str(s.get(k) or "") for k in
                      ("title", "summary", "source", "deadline", "prize",
                       "eligibility", "opportunity_type", "apply_url", "who_affected")]
    for block in (data.get("section_extras") or {}).values():
        for row in (block or {}).get("best_for") or []:
            parts += [str(v) for v in row.values()]
    return "\n".join(parts)


def stray_question_marks(pdf_text, src):
    """How many '?' the PDF has that the source does not.

    sanitize_text() maps anything outside latin-1 to '?', so an excess mark is a
    character that was silently dropped. Grepping for '?' cannot distinguish that
    from a real question, which is why every run used to re-read the same three
    sentences by hand; the arithmetic decides it outright.
    """
    return max(0, pdf_text.count("?") - src.count("?"))


def unfinished_summaries(data):
    """[(title, tail)] for summaries that do not end on a finished sentence."""
    out = []
    for stories in (data.get("sections") or {}).values():
        for s in stories or []:
            summary = s.get("summary") or ""
            if _is_truncated(summary):
                out.append((s.get("title", ""), summary.strip()[-60:]))
    return out


# Enough of a title to identify the story, short enough to survive _fit_title()
# truncating the longest ones. The shortest real title seen in an edition is
# ~35 characters once whitespace is squashed.
TITLE_PREFIX = 30


def missing_titles(data, pdf_text):
    """Story titles whose opening does not appear in the rendered page."""
    page = _squash(pdf_text)
    out = []
    for stories in (data.get("sections") or {}).values():
        for s in stories or []:
            title = s.get("title") or ""
            if not title:
                continue
            if _squash(title)[:TITLE_PREFIX] not in page:
                out.append(title)
    return out


def page_problem(pages):
    """The blocking problem for a PDF over the page limit, or None."""
    from generate_pdf import PAGE_LIMIT
    if pages > PAGE_LIMIT:
        return (f"the PDF is {pages} pages; the limit is {PAGE_LIMIT} - drop the stories "
                "write_analyzed() names under 'to fit, drop:' (never shorten an explanation), "
                "then rebuild")
    return None


def run_tests():
    """Run the plain-script test suite. Returns (ok, one-line-per-file report)."""
    lines, ok = [], True
    for path in sorted(glob.glob(os.path.join(TOOLS_DIR, "tests", "test_*.py"))):
        r = subprocess.run([sys.executable, path], capture_output=True, text=True)
        tail = (r.stdout.strip().splitlines() or ["no output"])[-1]
        lines.append(f"    {os.path.basename(path):32s} {tail}")
        if r.returncode != 0:
            ok = False
            lines.append("      " + r.stdout.strip()[:600])
    return ok, lines


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--send", action="store_true", help="email the PDF once it verifies")
    ap.add_argument("--skip-pdf", action="store_true", help="the PDF is already rendered")
    ap.add_argument("--skip-tests", action="store_true")
    args = ap.parse_args()

    with open(ANALYZED, encoding="utf-8") as f:
        data = json.load(f)
    today = datetime.now().strftime("%Y-%m-%d")
    problems = []

    print("1. test suite")
    if args.skip_tests:
        print("    skipped")
    else:
        ok, lines = run_tests()
        print("\n".join(lines))
        if not ok:
            problems.append("test suite failed")

    print("2. PDF")
    pdf_path = os.path.join(web_text.TMP_DIR, f"ai_news_daily_{today}.pdf")
    if args.skip_pdf:
        print(f"    skipped, using {os.path.basename(pdf_path)}")
    else:
        r = subprocess.run([sys.executable, os.path.join(TOOLS_DIR, "generate_pdf.py")],
                           capture_output=True, text=True)
        print("    " + " | ".join(l.strip() for l in r.stdout.strip().splitlines()[-3:]))
        if r.returncode != 0:
            problems.append("PDF generation failed: " + r.stderr.strip()[:300])
    if not os.path.exists(pdf_path):
        problems.append(f"no PDF at {pdf_path}")
        print("\n".join("  !! " + p for p in problems))
        return 1

    print("3. rendered text")
    from pypdf import PdfReader
    reader = PdfReader(pdf_path)
    pdf_text = "\n".join(p.extract_text() for p in reader.pages)
    src = source_text(data)

    stray = stray_question_marks(pdf_text, src)
    print(f"    {len(reader.pages)} pages | {len(pdf_text):,} chars extracted")
    too_long = page_problem(len(reader.pages))
    if too_long:
        problems.append(too_long)
    if stray:
        problems.append(f"{stray} stray '?' in the PDF that the source does not have "
                        "- a character outside latin-1 reached sanitize_text()")
    else:
        print(f"    stray '?': none ({pdf_text.count('?')} in the PDF, all present in the source)")

    cut = unfinished_summaries(data)
    if cut:
        for title, tail in cut:
            problems.append(f"summary ends mid-sentence [{title[:50]}]: ...{tail!r}")
    else:
        print("    every summary ends on a complete sentence")

    stories = sum(len(v or []) for v in (data.get("sections") or {}).values())
    missing = missing_titles(data, pdf_text)
    if missing:
        problems.append(f"{len(missing)} title(s) not found in the rendered PDF, e.g. {missing[0][:60]!r}")
    else:
        print(f"    all {stories} story titles present in the rendered PDF")

    print("4. quality review")
    # The 24h rule is measured here, against the clock at send - not against the
    # scrape. check_edition raises stale_story as an ERROR, so a run that drags
    # long enough to age its own stories out blocks itself instead of mailing them.
    lines = freshness_lines(data)
    if not lines:
        print("    freshness: no story carries a date")
    for line in lines:
        rule = f"{line['limit'] // 24}d" if line["limit"] >= 48 else f"{line['limit']}h"
        print(f"    freshness: oldest of {line['stories']:2d} stories on the {rule} rule "
              f"is {line['oldest']:.1f}h old")
    findings = check_edition(data, today=today)
    errors = [f for f in findings if f["severity"] == "ERROR"]
    warns = [f for f in findings if f["severity"] == "WARN"]
    for f in warns:
        print(f"    WARN  {f['code']:26s} [{f['section']}] {f['title'][:44]}")
        print(f"          {f['detail']}")
    for f in errors:
        problems.append(f"{f['code']} [{f['section']}] {f['title'][:50]}: {f['detail']}")
    print(f"    {len(errors)} error(s), {len(warns)} warning(s)")

    if problems:
        print("\nNOT SENT - fix these first:")
        for p in problems:
            print("  !!", p)
        return 1

    print("5. backup")
    backup = os.path.join(web_text.TMP_DIR, f"analyzed_content_{today}.bak.json")
    shutil.copy(ANALYZED, backup)
    print(f"    {os.path.basename(backup)}")

    print("6. delivery")
    if not args.send:
        print("    skipped (pass --send to mail it)")
        print(f"\nVERIFIED: {os.path.basename(pdf_path)}, {stories} stories, {len(reader.pages)} pages")
        return 0

    from send_email import send_email
    send_email()
    print(f"\nVERIFIED AND SENT: {os.path.basename(pdf_path)}, {stories} stories, "
          f"{len(reader.pages)} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
