"""Cases for the seventeen sections and the order they render in.

The 2 Oct 2026 restructure gave each of the four top AI companies its own
section (OpenAI, Google AI, Anthropic & Claude Code, xAI & Grok), split xAI out
of the Musk section, and put the sections in Rahul's own order. The order below
is that list, copied exactly; changing it is Rahul's decision, not a refactor.
On 2026-10-03 Rahul asked for the PDF to focus on landing a remote or
visa-sponsored Forward Deployed / Solutions Engineer role, so the careers
section (open roles and hiring news) was added and leads the edition.
On 2026-10-07 Rahul re-ranked them: jobs, hackathons, grants, OpenAI, Anthropic,
Grok, Gemini, open models, closed models, global, unaddressed problems,
automation, business opportunities, Elon Musk, Indian AI, RSI, quantum.

The description line under each section header is drawn with cell(), which does
not wrap, so a description wider than the 186 mm column runs past the margin.

Run: python3 tools/tests/test_sections.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fpdf import FPDF

from generate_pdf import SECTION_CONFIG, SECTION_ORDER, sanitize_text

EXPECTED_ORDER = [
    "fde_careers",                     # 0  Remote FDE & Solutions Jobs
    "ai_hackathons",                   # 1  AI Hackathons
    "product_showcase_opportunities",  # 2  AI Grants, Fellowships & Programs
    "openai_news",                     # 3  OpenAI
    "anthropic_claude_news",           # 4  Anthropic & Claude Code
    "xai_grok_news",                   # 5  xAI & Grok
    "google_ai_news",                  # 6  Google AI (Gemini)
    "open_model_landscape",            # 7  Open Models & Open Weights
    "closed_model_landscape",          # 8  Closed Models & Frontier APIs
    "global_ai_news",                  # 9  Global AI News
    "unaddressed_ai_problems",         # 10 Unaddressed AI Problems
    "ai_business_automation",          # 11 AI Automation & Business
    "ai_business_opportunities",       # 12 AI Business Opportunities
    "elon_musk_ai_vision",             # 13 Elon Musk on AI
    "indian_ai_industry",              # 14 Indian AI Industry
    "ai_self_improvement_rsi",         # 15 AI Self-Improvement (RSI)
    "quantum_ai_research",             # 16 Quantum + AI (Thursdays only)
]

DESC_MAX_MM = 186


def check(failures, cond, msg):
    if not cond:
        failures.append(msg)


def main():
    failures, cases = [], 0

    cases += 1
    check(failures, SECTION_ORDER == EXPECTED_ORDER,
          f"SECTION_ORDER is not Rahul's seventeen in Rahul's order: {SECTION_ORDER!r}")

    cases += 1
    check(failures, set(SECTION_ORDER) == set(SECTION_CONFIG),
          f"ORDER and CONFIG differ: {sorted(set(SECTION_ORDER) ^ set(SECTION_CONFIG))}")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "I", 8)
    for key in EXPECTED_ORDER:
        desc = (SECTION_CONFIG.get(key) or {}).get("desc", "")
        cases += 1
        width = pdf.get_string_width(sanitize_text(desc)) if desc else 0
        check(failures, desc and width <= DESC_MAX_MM,
              f"{key}: description empty or {width:.0f} mm wide, over the {DESC_MAX_MM} mm column")

    cases += 2
    xai_desc = (SECTION_CONFIG.get("xai_grok_news") or {}).get("desc", "").lower()
    musk_desc = (SECTION_CONFIG.get("elon_musk_ai_vision") or {}).get("desc", "").lower()
    check(failures, "musk" not in xai_desc,
          f"xAI & Grok is about the company, not Musk: {xai_desc!r}")
    check(failures, "xai" not in musk_desc,
          f"the Musk section is his own view on AI; xAI has its own section: {musk_desc!r}")

    cases += 1
    check(failures, (SECTION_CONFIG.get("elon_musk_ai_vision") or {}).get("label") == "Elon Musk on AI",
          "the Musk section's label must be 'Elon Musk on AI'")

    # The careers section: its open-roles table is drawn by the standing-table code.
    careers = SECTION_CONFIG.get("fde_careers") or {}
    cases += 2
    check(failures, "forward deployed" in careers.get("desc", "").lower()
          and "visa" in careers.get("desc", "").lower(),
          f"the careers section must say it covers FDE roles, remote or by visa: {careers!r}")
    check(failures, careers.get("table_heading"),
          "the careers section needs a heading for its open-roles table")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
