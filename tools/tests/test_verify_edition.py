"""Cases for verify_edition.py, which collapses the pre-send checks into one turn.

The 2026-09-17 run spent turns 76-110 - 35 model turns at 220-244k context, close
to 8M tokens - running the test suite, extracting the PDF, eyeballing it, taking
the backup and inspecting the mail tool, one command at a time. All of it is
mechanical and now runs in one call.

The stray-'?' check is the interesting one. The workflow used to say "grep the
rendered text for ?", which cannot tell an encoding artefact from a real question
mark, so every run re-litigated the same three sentences by hand. Counting the
PDF's question marks against the source JSON's answers it exactly: any excess was
manufactured by sanitize_text() dropping a character it could not map to latin-1.

Run: python3 tools/tests/test_verify_edition.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verify_edition import (missing_titles, source_text, stray_question_marks,
                            unfinished_summaries)

EDITION = {
    "sections": {
        "global_ai_news": [
            {"title": "Did Anthropic ship hooks?", "summary": "Yes. It shipped them on Tuesday.",
             "source": "The Verge", "url": "https://example.com/a", "published_date": "2026-09-16"},
        ],
        "ai_hackathons": [
            {"title": "Hack Apertus", "summary": "A Swiss hackathon. It closes in October.",
             "source": "Devpost", "url": "https://x.dev", "deadline": "16 Oct 2026"},
        ],
    }
}


def check(failures, ok, message):
    if not ok:
        failures.append(message)


def main():
    failures = []
    cases = 0

    src = source_text(EDITION)
    cases += 2
    check(failures, "Did Anthropic ship hooks?" in src, "source_text dropped a title")
    check(failures, src.count("?") == 1, f"source_text ? count = {src.count('?')} (expected 1)")

    # The PDF reproduces the one real question mark: clean.
    clean_pdf = "GLOBAL AI NEWS\nDid Anthropic ship hooks?\nYes. It shipped them on Tuesday."
    cases += 1
    check(failures, stray_question_marks(clean_pdf, src) == 0,
          "a real question mark was reported as an artefact")

    # sanitize_text() turned an unmappable character into '?': one excess mark.
    dirty_pdf = clean_pdf + "\nRs?50,000 prize for the caf? demo"
    cases += 1
    check(failures, stray_question_marks(dirty_pdf, src) == 2,
          f"expected 2 stray marks, got {stray_question_marks(dirty_pdf, src)}")

    # An artefact that happens to sit where a real one would still counts,
    # because the arithmetic does not care where in the page it landed.
    cases += 1
    check(failures, stray_question_marks(clean_pdf + " ?", src) == 1,
          "excess count is wrong when the artefact trails the text")

    # Summaries that stop mid-sentence, the other thing the run checked by eye.
    bad = {"sections": {"global_ai_news": [
        {"title": "Fine", "summary": "A complete thought. And another one."},
        {"title": "Cut", "summary": "The company said it would"},
        {"title": "Ellipsis", "summary": "The company said it would..."},
    ]}}
    names = [t for t, _ in unfinished_summaries(bad)]
    cases += 3
    check(failures, "Cut" in names, f"mid-sentence summary missed: {names}")
    check(failures, "Ellipsis" in names, f"trailing ellipsis missed: {names}")
    check(failures, "Fine" not in names, f"complete summary flagged: {names}")

    # Titles reach the page through two transforms that the check must tolerate:
    # sanitize_text() folds a curly apostrophe to a straight one, multi_cell()
    # wraps long titles across lines, and _fit_title() truncates the longest ones
    # with an ellipsis. Comparing whole titles flagged 8 good stories on the
    # 2026-09-17 edition; only a prefix is meaningful.
    rendered = ("SQC's Quantum Machine Learning Cuts Chip\nDesign Time From Hours To Minutes\n"
                "Generalized Agent Iteration: One Formal Framework for Iterative Policy...")
    edition = {"sections": {"quantum_ai_research": [
        {"title": "SQC’s Quantum Machine Learning Cuts Chip Design Time From Hours To Minutes"},
        {"title": "Generalized Agent Iteration: One Formal Framework for Iterative Policy "
                  "Improvement in Self-Referential Systems"},
        {"title": "A story that never made it onto any page at all"},
    ]}}
    missing = missing_titles(edition, rendered)
    cases += 3
    check(failures, not any("SQC" in t for t in missing),
          f"curly apostrophe / line wrap flagged as missing: {missing}")
    check(failures, not any(t.startswith("Generalized") for t in missing),
          f"_fit_title truncation flagged as missing: {missing}")
    check(failures, any(t.startswith("A story that never") for t in missing),
          f"a genuinely absent title was not caught: {missing}")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
