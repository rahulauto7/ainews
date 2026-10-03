"""Cases for check_quality.py, the deterministic replacement for the four
adversarial reviewer agents retired on 2026-09-17.

Those reviewers cost ~4M tokens per run - 25% of the whole pipeline - because
the main thread polled them at 240k context, and on 2026-09-17 they burned the
session limit without ever returning a verdict. Everything they reliably caught
was mechanical, so it is checked here instead, in one turn and offline.

Severity matters: ERROR blocks the send, WARN is printed for a human glance.
A check that fires on good copy is worse than no check, so every WARN case
below has a matching clean case that must NOT fire.

Run: python3 tools/tests/test_check_quality.py
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from check_quality import check_edition

# The clock is pinned alongside `today`. Without it `check_edition` reads the
# real one, so the freshness gate aged this file's fixtures into a
# `stale_story` ERROR the day after it was written (caught 2026-09-18).
NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)

GOOD = (
    "Anthropic, the San Francisco AI company behind the Claude family of models, has added "
    "hooks to Claude Code, its command-line coding tool. A hook is a small script the tool runs "
    "automatically at a fixed point, such as just before it edits a file, so a team can enforce "
    "its own rules without changing the tool itself. The feature arrived because enterprise "
    "customers wanted an audit trail of every change an AI agent makes to their codebase. "
    "Anthropic says the hooks run locally and never send code to its servers.\n\n"
    "Until now, a company that wanted Claude Code to follow house rules had to write them into "
    "a long instruction file and hope the model obeyed. A hook is different because it is "
    "ordinary code that always runs, so a rule such as never touching the payments folder holds "
    "every time. Rival tools from GitHub and Google have added similar controls this year, as "
    "businesses hand more of their routine coding to AI agents. Anthropic said the feature is "
    "available today to every Claude Code user at no extra cost."
)


def story(**over):
    s = {"title": "Anthropic ships hooks", "summary": GOOD, "source": "The Verge",
         "url": "https://example.com/a", "relevance": 5, "tags": ["anthropic"],
         "published_date": "2026-09-16"}
    s.update(over)
    return s


def edition(sections, extras=None):
    return {"sections": sections, "section_extras": extras or {},
            "section_labels": {}, "analyzed_at": "2026-09-17T00:00:00+00:00"}


def codes(findings, severity=None):
    return sorted({f["code"] for f in findings if severity is None or f["severity"] == severity})


def check(failures, ok, message):
    if not ok:
        failures.append(message)


def main():
    failures = []
    cases = 0

    # A clean edition fires nothing at all. This is the case that keeps the
    # linter honest - noisy checks get ignored, and an ignored check is dead.
    clean = edition({"global_ai_news": [story(), story(title="B", url="https://example.com/b"),
                                        story(title="C", url="https://example.com/c")]})
    found = check_edition(clean, today="2026-09-17", now=NOW)
    cases += 1
    check(failures, found == [], f"clean edition should fire nothing, got {codes(found)}")

    # ERROR: the banned strategy-note framing removed on 2026-09-03.
    for phrase in ("Automation angle: build a wrapper for this.",
                   "Why it matters for you: you could ship this in a weekend.",
                   "The opportunity is to resell this to Indian SMBs."):
        bad = edition({"global_ai_news": [story(summary=GOOD + " " + phrase)]})
        found = check_edition(bad, today="2026-09-17", now=NOW)
        cases += 1
        check(failures, "banned_phrase" in codes(found, "ERROR"),
              f"banned phrase not caught: {phrase!r} -> {codes(found)}")

    # ERROR: a summary that stops mid-sentence.
    for tail in ("The company said it would", "The company said it would...", "According to"):
        bad = edition({"global_ai_news": [story(summary=GOOD[:400] + " " + tail)]})
        found = check_edition(bad, today="2026-09-17", now=NOW)
        cases += 1
        check(failures, "truncated" in codes(found, "ERROR"),
              f"truncation not caught: {tail!r} -> {codes(found)}")

    # ERROR: the same story printed in two sections.
    dup = edition({"global_ai_news": [story()], "indian_ai_industry": [story()]})
    found = check_edition(dup, today="2026-09-17", now=NOW)
    cases += 1
    check(failures, "duplicate_across_sections" in codes(found, "ERROR"),
          f"cross-section duplicate not caught: {codes(found)}")

    # ...but the same story is allowed to appear once.
    cases += 1
    check(failures, "duplicate_across_sections" not in codes(check_edition(clean, today="2026-09-17", now=NOW)),
          "duplicate check fired on a single appearance")

    # WARN: an acronym never expanded anywhere in its summary.
    jargon = GOOD.replace("hooks to Claude Code", "MCP support to Claude Code")
    found = check_edition(edition({"global_ai_news": [story(summary=jargon)]}), today="2026-09-17", now=NOW)
    cases += 1
    check(failures, "unexplained_acronym" in codes(found, "WARN"),
          f"unexpanded acronym not caught: {codes(found)}")

    # ...but not when the summary expands it, and never for everyday ones.
    expanded = jargon.replace("MCP support", "Model Context Protocol (MCP) support")
    found = check_edition(edition({"global_ai_news": [story(summary=expanded)]}), today="2026-09-17", now=NOW)
    cases += 1
    check(failures, "unexplained_acronym" not in codes(found),
          f"acronym check fired on an expanded term: {[f['detail'] for f in found]}")

    # ...nor when the expansion carries the connector words English actually uses.
    # "Society of Automotive Engineers" is how SAE is written, and the first
    # version of this check demanded strictly consecutive capitalised words, so
    # it fired on five correctly-glossed terms in the 2026-09-18 edition.
    for gloss in ("SAE, the Society of Automotive Engineers, rates",
                  "METR, short for Model Evaluation and Threat Research, ranks",
                  "a system called SMART, for Strategic Management of Airspace, Routes and "
                  "Trajectories, flags",
                  "the Institute for AI Policy and Strategy, or IAPS, runs",
                  "UNICEF, the United Nations Children's Fund, benchmarked"):
        glossed = GOOD.replace("has added", gloss + " it and has added")
        found = check_edition(edition({"global_ai_news": [story(summary=glossed)]}),
                              today="2026-09-17", now=NOW)
        cases += 1
        check(failures, "unexplained_acronym" not in codes(found),
              f"acronym check fired on a glossed term: {gloss!r} -> "
              f"{[f['detail'] for f in found]}")

    # ...nor when the expansion comes first and the acronym is introduced with
    # "or", which is how a term whose initials skip words gets defined:
    # "video memory, or VRAM" gives the initials test only V and M.
    for pre_gloss in ("video memory, or VRAM, caps",
                      "the covering design problem, or CDP, limits"):
        glossed = GOOD.replace("has added", pre_gloss + " it and has added")
        found = check_edition(edition({"global_ai_news": [story(summary=glossed)]}),
                              today="2026-09-17", now=NOW)
        cases += 1
        check(failures, "unexplained_acronym" not in codes(found),
              f"acronym check fired on a pre-glossed term: {pre_gloss!r} -> "
              f"{[f['detail'] for f in found]}")

    # ...nor on a filename. AGENTS.md and CLAUDE.md are names on disk, and both
    # were flagged as unexplained acronyms in the 2026-09-22 run.
    for filename in ("AGENTS.md", "CLAUDE.md", "README.md"):
        named = GOOD.replace("hooks to Claude Code", f"{filename} support to Claude Code")
        found = check_edition(edition({"global_ai_news": [story(summary=named)]}),
                              today="2026-09-17", now=NOW)
        cases += 1
        check(failures, "unexplained_acronym" not in codes(found),
              f"acronym check fired on filename {filename!r}: {[f['detail'] for f in found]}")

    # ...and a bare acronym with a nearby capitalised phrase that is NOT its
    # expansion still fires. Loosening the rule must not empty it.
    # "or PQR support" has no comma after the token, so it is not the
    # appositive form the pre-gloss branch accepts.
    for bare in ("PQR support", "ZZQ compliance", "a choice of vendor, or PQR support,"):
        found = check_edition(edition({"global_ai_news": [story(summary=GOOD.replace(
            "hooks to Claude Code", bare + " to Claude Code"))]}), today="2026-09-17", now=NOW)
        cases += 1
        check(failures, "unexplained_acronym" in codes(found, "WARN"),
              f"unexpanded acronym {bare!r} slipped through: {codes(found)}")

    everyday = GOOD.replace("the San Francisco AI company", "the US AI company whose CEO")
    found = check_edition(edition({"global_ai_news": [story(summary=everyday)]}), today="2026-09-17", now=NOW)
    cases += 1
    check(failures, "unexplained_acronym" not in codes(found),
          f"acronym check fired on everyday terms: {[f['detail'] for f in found]}")

    # ERROR: a summary under the 1,000-character floor is not a full explanation
    # (rahul, 2026-10-03: five-line summaries sent him elsewhere to understand them).
    five_lines = GOOD.split("\n\n")[0]
    found = check_edition(edition({"global_ai_news": [story(summary=five_lines)]}),
                          today="2026-09-17", now=NOW)
    cases += 2
    check(failures, "short_summary" in codes(found, "ERROR"),
          f"a {len(five_lines)}-character summary must block the send: {codes(found)}")
    check(failures, len(GOOD) >= 1000 and "short_summary" not in codes(check_edition(
        edition({"global_ai_news": [story()]}), today="2026-09-17", now=NOW)),
          f"a {len(GOOD)}-character summary is a full explanation")

    # WARN: a sentence too long to follow in plain language, and not on GOOD.
    rambling = GOOD + (" The company said that the hooks, which it had been testing with a small "
                       "group of large customers in banking and retail for several months before "
                       "this week's release, would later be extended to cover the other tools it "
                       "sells, including its chat app and its developer platform, once it had "
                       "gathered enough feedback from those early users about how they work.")
    found = check_edition(edition({"global_ai_news": [story(summary=rambling)]}),
                          today="2026-09-17", now=NOW)
    cases += 1
    check(failures, "long_sentence" in codes(found, "WARN"),
          f"a 60-word sentence must be flagged: {codes(found)}")

    # WARN: fewer than the seven sentences the summary rules require.
    short = "Anthropic shipped hooks. They run locally. " + "Teams can enforce rules with them. "
    found = check_edition(edition({"global_ai_news": [story(summary=short * 4)]}), today="2026-09-17", now=NOW)
    cases += 1
    check(failures, "too_few_sentences" not in codes(found),
          "sentence check fired on a summary with plenty of sentences")

    three = "Anthropic shipped hooks for Claude Code, its coding tool. " * 3
    found = check_edition(edition({"global_ai_news": [story(summary=three)]}), today="2026-09-17", now=NOW)
    cases += 1
    check(failures, "too_few_sentences" in codes(found, "WARN"),
          f"three-sentence summary not caught: {codes(found)}")

    # WARN: the open-model table gone stale.
    stale = edition({"global_ai_news": [story()]},
                    {"open_model_landscape": {"as_of": "2026-08-20", "best_for": [{"model": "M"}]}})
    found = check_edition(stale, today="2026-09-17", now=NOW)
    cases += 1
    check(failures, "stale_best_for" in codes(found, "WARN"),
          f"stale best_for not caught (28 days): {codes(found)}")

    fresh = edition({"global_ai_news": [story()]},
                    {"open_model_landscape": {"as_of": "2026-09-14", "best_for": [{"model": "M"}]}})
    found = check_edition(fresh, today="2026-09-17", now=NOW)
    cases += 1
    check(failures, "stale_best_for" not in codes(found),
          f"best_for check fired at 3 days old: {codes(found)}")

    # Findings carry enough to act on without opening the JSON.
    bad = edition({"global_ai_news": [story(title="Needle", summary=GOOD + " Automation angle: x.")]})
    f = check_edition(bad, today="2026-09-17", now=NOW)[0]
    cases += 3
    check(failures, f.get("section") == "global_ai_news", f"finding has no section: {f!r}")
    check(failures, "Needle" in (f.get("title") or ""), f"finding has no title: {f!r}")
    check(failures, f.get("detail"), f"finding has no detail: {f!r}")

    for fl in failures:
        print("FAIL:", fl)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
