"""Cases for the token-saving curation tools added on 2026-09-15.

Every page shape below is one that broke a simpler extractor on that day's feed:
BBC splits its story across sibling blocks, Inc42 puts course adverts in an
<article> element above the real story, and Economic Times has no <p> tags at
all, only JSON-LD. All cases are offline.

Run: python3 tools/tests/test_curation_tools.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import builder_helpers
import web_text
from find_opportunities import _norm_url, _usd
from scrape_rss_feeds import plain_summary

LEDE = "An artificial intelligence kill switch which can be checked by a third party may need to be mandatory."
SECOND = "Jack Clark, one of seven founders of Anthropic, told the BBC that verification should be independent."
THIRD = "Clark said specifics around kill switch requirements should be part of the larger policy conversation."

BBC_LIKE = f"""<html><head><meta property="article:published_time" content="2026-09-14T08:00:00Z"></head>
<body><article>
  <div class="block"><p>{LEDE}</p></div>
  <div class="block"><p>{SECOND}</p></div>
  <div class="block"><p>{THIRD}</p><p>{THIRD.replace('Clark', 'He')}</p></div>
</article></body></html>"""

PROMO = "D2CX by Inc42 is a 12-week hands-on program to help you level up your D2C game today."
STORY = ("The finance ministry has notified amendments to the Payment and Settlement Systems Act, "
         "opening the door to a merchant discount rate on high-value UPI payments. ")
INC42_LIKE = f"""<html><body>
<article><p>{PROMO}</p><p>{PROMO.replace('D2CX', 'ManagementX')}</p></article>
<div class="single-post-content">{''.join(f'<p>{STORY}{n}</p>' for n in range(6))}</div>
</body></html>"""

ET_BODY = "Anthropic CEO Dario Amodei on Saturday called for a slowdown in advanced AI development. " * 8
ET_LIKE = f"""<html><head><script type="application/ld+json">
{json.dumps([{"@type": "NewsArticle", "datePublished": "2026-09-15T05:00:00+05:30", "articleBody": ET_BODY}])}
</script></head><body><div>Benchmarks CLOSED Nifty 23,398.10</div><p>Listen to this article</p></body></html>"""


def check(failures, ok, message):
    if not ok:
        failures.append(message)


def main():
    failures = []
    cases = 0

    # Article extraction
    r = web_text.extract_article(BBC_LIKE)
    cases += 2
    check(failures, r["text"].startswith(LEDE), f"BBC-like: lede lost, text starts {r['text'][:60]!r}")
    check(failures, r["published"] == "2026-09-14", f"BBC-like: published {r['published']!r}")

    r = web_text.extract_article(INC42_LIKE)
    cases += 1
    check(failures, "finance ministry" in r["text"] and "D2CX" not in r["text"],
          f"Inc42-like: promo kept or story lost: {r['text'][:80]!r}")

    r = web_text.extract_article(ET_LIKE)
    cases += 2
    check(failures, r["text"].startswith("Anthropic CEO Dario Amodei"), f"ET-like: {r['text'][:60]!r}")
    check(failures, r["published"] == "2026-09-15", f"ET-like: published {r['published']!r}")

    # grep_context: overlapping matches merge, merged snippets are capped
    text = "Deadline: Oct 23. " + "x" * 50 + " deadline again " + "y" * 2000
    snips = web_text.grep_context(text, "deadline", width=60, max_len=200)
    cases += 2
    check(failures, len(snips) == 1, f"grep_context: expected one merged snippet, got {len(snips)}")
    check(failures, all(len(s) <= 206 for s in snips), "grep_context: snippet not capped")

    # Scraper: tags are stripped before the summary is cut
    raw = '<p><img src="https://example.com/' + "a" * 480 + '.jpg" alt=""></p><p>' + "Real text. " * 40 + "</p>"
    got = plain_summary(raw)
    cases += 2
    check(failures, got.startswith("Real text.") and len(got) > 300,
          f"plain_summary: image tag ate the text: {got[:60]!r} ({len(got)} chars)")
    check(failures, len(plain_summary("word " * 1000)) <= 1500, "plain_summary: not capped at 1,500")

    # Opportunity helpers
    cases += 3
    check(failures, _usd("$138,000") == 138000, f"_usd $: {_usd('$138,000')}")
    check(failures, 580 < _usd("₹ 50,000") < 600, f"_usd ₹: {_usd('₹ 50,000')}")
    check(failures, _norm_url("https://www.Example.com/apply/") == _norm_url("example.com/apply"),
          "_norm_url: www/scheme/trailing slash should not matter")

    # Carry-forward relabels "New today:" rows (Lessons 2026-09-13)
    with tempfile.TemporaryDirectory() as tmp:
        saved = web_text.TMP_DIR
        web_text.TMP_DIR = tmp
        try:
            edition = {"sections": {}, "section_extras": {"open_model_landscape": {
                "as_of": "2026-09-11",
                "best_for": [{"use_case": "Coding", "model": "M", "maker": "X", "licence": "MIT",
                              "why": "New today: tops the leaderboard."}]}}}
            for name in ("analyzed_content_2026-09-13.bak.json", "analyzed_content_2026-09-15.bak.json"):
                with open(os.path.join(tmp, name), "w") as f:
                    json.dump(edition, f)
            editions = builder_helpers.prior_editions("2026-09-15")
            block = builder_helpers.carry_forward_best_for("2026-09-15")
        finally:
            web_text.TMP_DIR = saved
    cases += 3
    check(failures, [d for d, _ in editions] == ["2026-09-13"],
          f"prior_editions must exclude the run's own date: {[d for d, _ in editions]}")
    check(failures, block and block["best_for"][0]["why"] == "Carried forward: tops the leaderboard.",
          f"carry_forward_best_for: {block and block['best_for'][0]['why']!r}")
    check(failures, block and block["as_of"] == "2026-09-11", "carry_forward_best_for: as_of must not change")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
