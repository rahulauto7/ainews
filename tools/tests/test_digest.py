"""Cases for the digest: grouped in section order and capped per group.

With 200+ sources the scrape returns far more than the curator can read, so
.tmp/digest.md shows the best-carried stories of each group and counts the rest.
The cap limits what the curator reads, never how many stories a section prints.
The group order follows the sixteen PDF sections, and each group's label names
the section it feeds after "->".

Run: python3 tools/tests/test_digest.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import feed_sources
import news_digest
from generate_pdf import SECTION_CONFIG


def check(failures, cond, msg):
    if not cond:
        failures.append(msg)


def art(source, count=1, published="2026-10-02T08:00:00+00:00", title="A story"):
    return {"title": title, "source": source, "duplicate_count": count, "published": published}


def main():
    failures, cases = [], 0
    order = news_digest.CATEGORY_ORDER
    groups = [c for c, _ in order]

    # ── 1. Every category the registry uses has a group ──────────────────────
    used = {r[2] for r in feed_sources.RSS} | {e[1] for e in feed_sources.EXTRA}
    cases += 1
    check(failures, used <= set(groups), f"categories with no digest group: {sorted(used - set(groups))}")

    # ── 2. Every section is named by some group ──────────────────────────────
    targets = " | ".join(label.split("->", 1)[1] for _, label in order if "->" in label)
    for key, config in SECTION_CONFIG.items():
        cases += 1
        check(failures, config["label"] in targets, f"no digest group feeds {config['label']!r} ({key})")

    # ── 3. Ranking inside a group ────────────────────────────────────────────
    ranked = getattr(news_digest, "ranked", None)
    cap_for = getattr(news_digest, "cap_for", None)
    short_source = getattr(news_digest, "short_source", None)
    if not (ranked and cap_for and short_source):
        failures.append("news_digest lacks ranked / cap_for / short_source")
        cases += 1
    else:
        items = [(0, art("The Verge AI", 1, title="one outlet")),
                 (1, art("The Verge AI", 5, title="five outlets"))]
        cases += 1
        check(failures, [a["title"] for _, a in ranked(items)][0] == "five outlets",
              "a story carried by five outlets must come before one carried by one")

        items = [(0, art("OpenAI (via Google News)", 2, title="proxy")),
                 (1, art("TechCrunch AI", 2, title="direct"))]
        cases += 1
        check(failures, [a["title"] for _, a in ranked(items)][0] == "direct",
              "at equal count a direct feed comes before a Google News copy")

        items = [(0, art("TechCrunch AI", 1, "2026-10-02T01:00:00+00:00", "older")),
                 (1, art("TechCrunch AI", 1, "2026-10-02T09:00:00+00:00", "newer"))]
        cases += 1
        check(failures, [a["title"] for _, a in ranked(items)][0] == "newer",
              "at equal count and kind the newer story comes first")

        # ── 4. Caps ──────────────────────────────────────────────────────────
        cases += 3
        check(failures, cap_for("general") == 60, f"cap_for('general') = {cap_for('general')}")
        check(failures, cap_for("openai") == 40, f"cap_for('openai') = {cap_for('openai')}")
        check(failures, cap_for("video") == 30, f"cap_for('video') = {cap_for('video')}")

        # ── 5. Short source names ────────────────────────────────────────────
        cases += 4
        x = short_source("Sam Altman on X (via Google News)")
        bing = short_source("OpenAI (via Bing News)")
        check(failures, x.startswith("X-"), f"an X search must read X-...: {x!r}")
        check(failures, bing.startswith("Bing-"), f"a Bing search must read Bing-...: {bing!r}")
        check(failures, short_source("Anthropic News (via Google News)").startswith("GN-"),
              "a Google News search must read GN-...")
        check(failures, all(len(short_source(n)) <= 22 for n, *_ in feed_sources.RSS),
              "every short source name must fit 22 characters")

    cases += 1
    check(failures, news_digest.snippet({"source": "OpenAI (via Bing News)", "title": "T",
                                         "summary": "A long Bing description " * 10}) == "",
          "Bing items carry Bing's own blurb, not the article, so no snippet")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
