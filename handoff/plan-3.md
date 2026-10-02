# Plan part 3 — hackathon platforms, X posts, workflow doc, proof on real data

CURRENT · written Fri 2 Oct 2026 · nothing below is implemented yet · follows `plan-2.md`.

## Task 6 — hackathons: lablab.ai, newest on Devpost, Devfolio, Unstop
**Files:** `tools/find_opportunities.py` (new `platforms` subcommand beside `devpost`, `check`, `recheck`),
`tools/prep_run.py` (task list at line 137), new `tools/tests/test_hackathon_platforms.py`.
Recipes and endpoints: `handoff/recipes.md`.

`python3 tools/find_opportunities.py platforms` prints four blocks. `prep_run.py` runs it in parallel with
the digest and writes `.tmp/hackathons.txt`, reported on one line the way `devpost` is. The existing
`.tmp/devpost.txt` (largest prize first) and `.tmp/recheck.txt` stay as they are.

1. **lablab.ai** — `parse_lablab_listing(html, now)` returns the events that have not ended, soonest
   deadline first, each with slug, start, end and signup flag. Then pass
   `https://lablab.ai/ai-hackathons/<slug>` for each to the existing `check(urls)` (line 147), which prints
   the prize, eligibility and deadline lines from the event page. Take the event's name from its page.
2. **Devpost, newest** — the same API as `devpost()` with `search=AI` and `order_by=recently-added` and no
   theme filter. Print the events the theme listing does not already show. This is the "new hackathons"
   view he asked for.
3. **Devfolio** and 4. **Unstop** — endpoints in the recipes. Their field names beyond the ten seen on
   2 Oct are not known: print one record's keys, then format title, dates, prize and URL.

Mark each line `printed mm-dd` or `rejected mm-dd: reason` from `history()`, as `devpost()` does. Wrap each
block so one platform failing prints `!! <platform>: <error>` and the other three still print. The
eligibility rules and the cash-prize check in the workflow are unchanged: lablab prize lines often mix
cash and credits ("$5k cash + $5k credits"), so the event page decides.

**`test_hackathon_platforms.py` cases** — build the fixture the way the page is built: put two event
records in one string, then `chunk = json.dumps(payload)[1:-1]` and
`html = f'<script>self.__next_f.push([1,"{chunk}"])</script>'`. Key order per record, as on the real page:
`"name":"…", … "signupActive":true, "oneCouponPerParticipant":false, "endAt":"2026-10-18T19:00:00.000Z",
"startAt":"2026-10-12T19:00:00.000Z", "toBeAnnounced":false, … "slug":"amd-developer-hackathon-act-iii",
"previousSlugs":[], "teamsActive":true, "type":"HACKATHON"`.
1. One event ended in 2025 and one ends 2026-10-18, with `now` = 2026-10-02: only the open one is returned,
   with its slug, both dates and `signup` True. Fails today: the function does not exist.
2. A page with no `__next_f` chunks returns `[]` and does not raise.
3. An event with `"type":"WORKSHOP"` is left out.

## Task 7 — read X posts in full
**Files:** `tools/web_text.py`, `tools/fetch_articles.py` (lines 61-62, 79-90, 93-105), new
`tools/tests/test_x_posts.py`. Recipe: `handoff/recipes.md`.

Today an X link is marked `X POST` and not fetched, so a Musk post is known only by the headline Google
News gives it, and its date is the day Google saw it. The keyless embed endpoint returns the whole post.

- `web_text.tweet_id(url)` returns the digits after `/status/`, or None.
- `web_text._tweet_token(tweet_id)` — the token function in the recipes, copied exactly.
- `web_text.fetch_tweet(url)` — GET the endpoint with `HEADERS`, return the JSON, raise on non-200.
- `web_text.tweet_record(js)` — pure: `{"title": "@<screen_name> on X", "text": <text>, "published":
  created_at[:10], "published_at": created_at}`. Append `Quoted post: <quoted_tweet.text>` and
  `In reply to @<in_reply_to_screen_name>` to the text when those keys are present.
- `fetch_articles.fetch_one()`: for an x.com or twitter.com URL call `fetch_tweet`; on success fill the
  record from `tweet_record` and set `rec["x_post"] = True`; on any failure keep today's behaviour
  (`rec["error"] = "X POST"`), so a failed read never aborts the batch.
- `render()`: for an X post print `published_at` on the head line. The curator passes it to
  `S(..., published_at=...)`, so the 24-hour gate measures the post's own time.
- `flags_for()`: do not flag an X post `THIN`; a post is short by nature.

**`test_x_posts.py` cases**
1. `tweet_id("https://x.com/elonmusk/status/2105929186556998055") == "2105929186556998055"`; a URL with no
   status returns None. Fails today: the function does not exist.
2. `_tweet_token("2105929186556998055")` is a non-empty string of lowercase letters and digits with no "0"
   and no ".".
3. `tweet_record` on a fixture with `created_at`, `text`, `user.screen_name`, `quoted_tweet.text` and
   `in_reply_to_screen_name`: the text contains the quoted post and the reply line, and `published_at`
   equals `created_at`.
4. `flags_for` on a record with `x_post` True and 80 characters of text does not include `THIN`.

## Task 8 — bring `workflows/daily_ai_news.md` in line
Updating this file was part of the approved design. Edit in place; do not rewrite the Lessons.
1. **Objective** (lines 3-10): 16 sections, 15 on days without Quantum.
2. **Step 1** (lines 68-78): outputs gain `.tmp/hackathons.txt`; replace "34 feeds" with the registry.
3. **Step 2**: the digest follows the 16 sections and is capped per group; `fetch_articles.py` now reads X
   posts in full, so update the `X POST` flag text.
4. **"The 12 PDF Sections"** (lines 127-144) becomes "The 16 PDF Sections" in the new order, one line each,
   then the routing rule: a story prints once. Company news goes to that company's section; a cross-vendor
   comparison, benchmark or price table goes to Closed Models; an open-weight release goes to Open Models
   whoever made it; what Musk himself says goes to Elon Musk on AI; xAI company and product news goes to
   xAI & Grok; Global AI News takes the rest (governments, Meta, Microsoft, NVIDIA, Apple, Chinese labs).
5. **Summary Quality Rules** (lines 166-179): replace the "4-7 complete sentences ... `clip_to_sentence()`
   cuts at 1,200" bullet with: at least four complete sentences and no upper limit; extend the explanation
   whenever a term, a mechanism or the background would otherwise send the reader to another site; the
   test is whether he could explain the story to someone else after reading only that paragraph; extra
   length goes on explaining the news, never on advice. Replace "If time is short, cut story count" with:
   there is no page limit; never shorten an explanation or drop a story to save space; a section runs
   short only when nothing else inside its freshness window qualifies.
6. **Section-Specific Rules** (lines 229-293): add `openai_news`, `google_ai_news`, `xai_grok_news`;
   rewrite `elon_musk_ai_vision` as Musk's own point of view (his posts, interviews, podcasts, talks, and
   statements the press reports; say what he actually said and the context; read each post in full and
   date it by the post's own timestamp); under `ai_hackathons` add `.tmp/hackathons.txt` as a source.
7. **Adding Sources** (lines 312-313): rows go in `tools/feed_sources.py`; explain the flags, the keyless
   rule, and that rejected sources are listed in that file.
8. **Troubleshooting** (lines 304-305) and the guard table (line 453): the renderer no longer shortens
   summaries; the guard is `test_summary_length.py`.
9. **Known Feed Issues** (lines 532-547): drop the ZDNet and xAI Blog line; add that X has no keyless
   feed, so coverage is the posts Google News has indexed.
10. **History**: add one entry dated the day the work is done: what changed, source count, digest size,
    test count.

## Task 9 — prove it on real data
1. `python3 tools/prep_run.py`. It must finish with the tests passing.
2. Read `.tmp/rss_scrape.log`. For each source on the `none from:` line: if `handoff/sources.txt` marks it
   `new-query`, fix the query or delete the row; if it is marked `live`, leave it (it posts less than
   daily); otherwise record it under Known Feed Issues. Note the source count and article count.
3. Check `.tmp/digest.md`: every one of the 21 groups that has articles appears, in section order, and the
   file is under about 35k tokens (`prep_run` prints the estimate). If it is larger, lower `DIGEST_CAP`.
4. Check `.tmp/hackathons.txt` lists lablab.ai's open events. Five were open on 2 Oct 2026: WeAreDevelopers
   x BAND (ends 6 Oct), AMD Developer Hackathon ACT III (18 Oct), TechEx Amsterdam (19 Oct), Vultr Agent
   Rush (8 Nov), Lablab x AMD AI Academy Challenge (1 Dec).
5. Pick one "Elon Musk ... on X" item from the digest and run `python3 tools/fetch_articles.py IDX`: the
   whole post and its timestamp must print.
6. **Sample edition** (Open question 1 in `HANDOFF.md`; default is to build it). Curate a real edition the
   normal way: all 16 sections (15 if it is not Thursday), 3-6 stories each, explanations at the new
   length. Then `python3 tools/verify_edition.py` WITHOUT `--send`. Give Rahul the PDF path and the page
   count. Do not email it.
7. Update `handoff/HANDOFF.md` (status, finished actions removed) and delete the memory note
   `news-restructure-plan-pending` once everything above is done.

**Definition of done:** the whole suite passes, with the new test files `test_sections.py`,
`test_summary_length.py`, `test_sources.py`, `test_digest.py`, `test_hackathon_platforms.py` and
`test_x_posts.py`; a real scrape has run on the new registry; the workflow describes what the code does;
and Rahul has a PDF to open, or has said to skip it.
