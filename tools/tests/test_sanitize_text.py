"""Cases for sanitize_text() in generate_pdf.py.

Helvetica in fpdf2 is latin-1 only, so anything outside it is replaced with "?".
The rupee sign did exactly that in every edition from 2026-09-08 to 2026-09-12
("cutting the cost of each from ?50 to ?5-15"), along with the euro sign and the
non-breaking hyphen. Each case below was found in a published analyzed_content.json.

Run: python3 tools/tests/test_sanitize_text.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generate_pdf import sanitize_text

CASES = [
    ("cutting the cost of each from ₹50 to ₹5-15", "cutting the cost of each from Rs 50 to Rs 5-15"),
    ("Prizes total ₹18 lakh (roughly $21,000)", "Prizes total Rs 18 lakh (roughly $21,000)"),
    ("Mistral raises €3B", "Mistral raises EUR 3B"),
    ("GPT‑6 Astra", "GPT-6 Astra"),
    ("posted on 𝕏", "posted on X"),
    # Invisible formatting characters print as "?" if not stripped. The word
    # joiner below is how YourStory titles arrive; the 2026-09-16 draft showed
    # "?Government to Match VC Investments in Indian Chip Startups".
    ("\u2060Government to Match VC Investments", "Government to Match VC Investments"),
    ("zero\u200bwidth\u200cspace\u200dmarks", "zerowidthspacemarks"),
    ("\ufeffleading BOM", "leading BOM"),
    ("bidi \u200emarks\u200f removed", "bidi marks removed"),
    # Letters outside latin-1 fold to their base letter. The 2026-09-24 draft
    # printed "Anadolu Ajans?" for the Turkish agency's Google News suffix.
    ("OpenAI chiefs tell UN - Anadolu Ajansı", "OpenAI chiefs tell UN - Anadolu Ajansi"),
    ("İstanbul and Başkent Üniversitesi", "Istanbul and Baskent Üniversitesi"),
    ("Łukasz from Łódź", "Lukasz from Lódz"),
    # latin-1 characters must pass through untouched
    ("a £10,000 stipend", "a £10,000 stipend"),
    # Emoji carry no words and are dropped, with the marks that build them:
    # variation selector, skin tone, keycap. X and YouTube titles keep theirs.
    ("Grok 5 training starts next month \U0001F680", "Grok 5 training starts next month "),
    ("Shipped \u2764\ufe0f today", "Shipped  today"),
    ("Thanks \U0001F44D\U0001F3FD team", "Thanks  team"),
    ("Top 1\ufe0f\u20e3 pick", "Top 1 pick"),
]


def main():
    failures = 0
    for raw, expected in CASES:
        got = sanitize_text(raw)
        if got != expected:
            failures += 1
            print(f"FAIL: {raw!r}\n  expected {expected!r}\n  got      {got!r}")
        if "?" in got and "?" not in raw:
            failures += 1
            print(f"FAIL: {raw!r} still produces '?': {got!r}")
    print(f"{len(CASES) - failures}/{len(CASES)} passed" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
