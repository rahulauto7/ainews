"""Cases for reading X posts in full.

Until 2026-10-02 an X link was marked X POST and never fetched, so a Musk post
was known only by the headline Google News gave it, dated the day Google saw it.
The keyless embed endpoint (cdn.syndication.twimg.com/tweet-result) returns the
whole post with its own timestamp; it needs the token computed below from the
post's id. All cases here are offline.

Run: python3 tools/tests/test_x_posts.py
"""

import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fetch_articles
import web_text

POST = {
    "created_at": "2026-10-01T18:22:11.000Z",
    "text": "Grok 5 training starts next month on the new cluster.",
    "user": {"screen_name": "elonmusk", "name": "Elon Musk"},
    "quoted_tweet": {"text": "xAI is hiring for the Memphis cluster."},
    "in_reply_to_screen_name": "sama",
}


def check(failures, cond, msg):
    if not cond:
        failures.append(msg)


def main():
    failures, cases = [], 0
    needed = ("tweet_id", "_tweet_token", "tweet_record", "fetch_tweet")
    missing = [n for n in needed if not hasattr(web_text, n)]
    if missing:
        print(f"FAIL: web_text lacks {', '.join(missing)}")
        print("1 failure(s) of 1")
        return 1

    # ── 1. The post id from a URL ────────────────────────────────────────────
    cases += 3
    check(failures, web_text.tweet_id("https://x.com/elonmusk/status/2105929186556998055")
          == "2105929186556998055", "tweet_id on an x.com post URL")
    check(failures, web_text.tweet_id("https://twitter.com/sama/status/123456789?s=20") == "123456789",
          "tweet_id on a twitter.com URL with a query string")
    check(failures, web_text.tweet_id("https://x.com/elonmusk") is None,
          "a profile URL has no post id")

    # ── 2. The embed token ───────────────────────────────────────────────────
    token = web_text._tweet_token("2105929186556998055")
    cases += 1
    check(failures, token and re.fullmatch(r"[a-z1-9]+", token),
          f"token must be lowercase letters and digits, no '0' and no '.': {token!r}")

    # ── 3. The record a post becomes ─────────────────────────────────────────
    rec = web_text.tweet_record(POST)
    cases += 5
    check(failures, rec["title"] == "@elonmusk on X", f"title: {rec['title']!r}")
    check(failures, POST["text"] in rec["text"], "the post's own text must be in the record")
    check(failures, "Quoted post: xAI is hiring for the Memphis cluster." in rec["text"],
          f"the quoted post must be in the text: {rec['text']!r}")
    check(failures, "In reply to @sama" in rec["text"], f"the reply line must be in the text: {rec['text']!r}")
    check(failures, rec["published_at"] == POST["created_at"] and rec["published"] == "2026-10-01",
          f"dates: {rec['published']!r} / {rec['published_at']!r}")

    plain = web_text.tweet_record({"created_at": POST["created_at"], "text": "Short post.",
                                   "user": {"screen_name": "sama"}})
    cases += 1
    check(failures, plain["text"] == "Short post.", f"no quote and no reply adds nothing: {plain['text']!r}")

    # ── 4. A post is short by nature: not THIN ───────────────────────────────
    x_rec = {"x_post": True, "text": "x" * 80, "published": "2026-10-01",
             "published_at": POST["created_at"], "url": "https://x.com/elonmusk/status/1"}
    flags = fetch_articles.flags_for(x_rec, datetime(2026, 10, 2))
    cases += 2
    check(failures, "THIN" not in flags, f"an X post must not be flagged THIN: {flags}")
    check(failures, "THIN" in fetch_articles.flags_for(dict(x_rec, x_post=False), datetime(2026, 10, 2)),
          "an 80-character article page is still THIN")

    # ── 5. The head line carries the post's own timestamp ────────────────────
    head = fetch_articles.render("7", x_rec, 0, datetime(2026, 10, 2)).splitlines()[0]
    cases += 1
    check(failures, POST["created_at"] in head, f"render must print published_at for a post: {head!r}")

    # ── 6. The curator's published_at dates the story on the page too ────────
    import builder_helpers
    saved, builder_helpers._ARTS = builder_helpers._ARTS, [{
        "title": "Grok 5 training starts next month - X", "url": "https://x.com/elonmusk/status/1",
        "source": "Elon Musk on X (via Google News)", "published": "2026-10-02T09:00:00+00:00",
        "published_date": "2026-10-02"}]
    try:
        story = builder_helpers.S(0, "Summary.", 4, ["musk"], published_at=POST["created_at"])
    finally:
        builder_helpers._ARTS = saved
    cases += 2
    check(failures, story["published_at"] == POST["created_at"], "S() must keep the post's timestamp")
    check(failures, story["published_date"] == "2026-10-01",
          f"the printed date must follow the post, not Google: {story['published_date']!r}")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
