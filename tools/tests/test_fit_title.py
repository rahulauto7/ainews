"""Cases for _fit_title() in generate_pdf.py.

Story titles were drawn with title[:95], which cut whatever character it landed on.
The 2026-09-14 edition printed "...in the week OpenAI ruled one out - The Ne" and
"...while everyone else bets the far". A character count also says nothing about
width: 95 bold capitals overflow the 155mm title cell. Both cases below are
headlines from that day's feed.

Run: python3 tools/tests/test_fit_title.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fpdf import FPDF

from generate_pdf import _fit_title

MAX_W = 155

# Titles that fit must come back unchanged. The first is 96 characters, so
# title[:95] cut it even though it fits the cell.
FITS = [
    "Perplexity trusts GPT-6 Astra with end-to-end systems",
    "Anthropic has chosen Nasdaq for its October IPO, in the week OpenAI ruled one out - The Next Web",
]
# Titles too wide for the cell must be shortened between words.
TOO_WIDE = [
    "Insight Partners' Devin Parekh on why the firm is diversifying while everyone else bets the farm "
    "on OpenAI and Anthropic - TechCrunch",
    "W" * 120,  # no spaces at all: must still fit
]


def main():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 9)
    failures = 0

    for raw in FITS:
        got = _fit_title(pdf, raw, MAX_W)
        if got != raw:
            failures += 1
            print(f"FAIL: a title that fits was changed: {got!r}")

    for raw in TOO_WIDE:
        got = _fit_title(pdf, raw, MAX_W)
        width = pdf.get_string_width(got)
        if width > MAX_W:
            failures += 1
            print(f"FAIL: {got!r} is {width:.1f}mm, wider than {MAX_W}mm")
        if not got.endswith("..."):
            failures += 1
            print(f"FAIL: shortened title does not say so: {got!r}")
        kept = got[:-3]
        if " " in raw and not raw.startswith(kept + " "):
            failures += 1
            print(f"FAIL: cut mid-word: {got!r}")

    total = len(FITS) + len(TOO_WIDE)
    print(f"{total}/{total} passed" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
