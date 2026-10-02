# Recipes — non-RSS readers, platform endpoints, rejected sources

CURRENT for tasks 3, 4, 6 and 7 · every recipe ran successfully on Fri 2 Oct 2026 unless it says otherwise.

## The four non-RSS readers (`EXTRA` in `tools/feed_sources.py`)
| name | category | kind | arg |
|---|---|---|---|
| Hacker News | social | hn | - |
| Hugging Face new models | open_model | hf_models | - |
| YouTube search: Elon Musk AI | elon_musk | yt_search | Elon Musk AI |
| YouTube search: AI news | video | yt_search | AI news |

Each reader takes `(name, arg, cutoff_time)` and returns the same article dicts as `articles_from_feed`
(`title`, `url`, `source`, `published` ISO, `published_date`, `summary`, `category`). It drops anything
older than the cutoff. On any error it prints one `  [ERROR] name: ...` line and returns `[]`, so one
broken page never stops the scrape. Keep the parsing in a pure function so it can be tested offline.

**Hacker News** (Algolia, keyless JSON) — GET `https://hn.algolia.com/api/v1/search` with `tags=story`,
`numericFilters=created_at_i>{cutoff_epoch},points>80`, `hitsPerPage=60`. Use `hits[].title`, `.url`
(fall back to `https://news.ycombinator.com/item?id={objectID}`), `.points`, `.created_at_i`. Keep only
`mentions_ai(title)`. 26 stories came back on 2 Oct, 2 of them about AI.

**Hugging Face new models** (keyless JSON) — GET
`https://huggingface.co/api/models?sort=likes7d&direction=-1&limit=100`. Items carry `id`, `createdAt`,
`likes`, `downloads`, `trendingScore`. The publish date is `createdAt`, so only models created inside the
window survive. Title `New on Hugging Face: {id}`, URL `https://huggingface.co/{id}`. This also prepares
for 13 Nov 2026, when r/LocalLLaMA's RSS feed ends.

**YouTube search** (public page, best effort) — GET `https://www.youtube.com/results` with
`search_query=<arg>` and `sp=CAISBAgCEAE=` (videos, uploaded today, newest first), browser User-Agent.
Take `var ytInitialData = (\{.*?\});</script>` with `re.S`, `json.loads` it, and walk every dict for a
`videoRenderer`: `videoId`, `title.runs[].text`, `publishedTimeText.simpleText` (seen as `13h ago`),
`ownerText.runs[0].text`. URL `https://www.youtube.com/watch?v={videoId}`; source is the channel name.
20 videos came back on 2 Oct. The page gives only a relative time, so take the older bound:
```python
_REL = re.compile(r"(\d+)\s*(minutes?|mins?|m|hours?|hrs?|h)\b", re.I)

def relative_to_datetime(text, now):
    """'13h ago' covers 13:00-13:59 ago, so the older bound is used. Days and months return None."""
    m = _REL.search(text or "")
    if not m:
        return None
    n = int(m.group(1)) + 1
    return now - (timedelta(minutes=n) if m.group(2).lower().startswith("m") else timedelta(hours=n))
```
Cases: `13h ago` gives now minus 14 hours; `5 minutes ago` gives now minus 6 minutes; `2 days ago` and
`3 months ago` give None, and an undated entry is dropped like any other.

**YouTube channel feeds** are ordinary Atom and sit in `sources.txt`:
`https://www.youtube.com/feeds/videos.xml?channel_id=UC…`; `entry.summary` is the video description. To
add a channel, fetch `https://www.youtube.com/@handle` and match `"channelId":"(UC[\w-]{22})"`.

**Bing News** rows are ordinary RSS but need the browser User-Agent, and each link is a tracking URL
(`bing.com/news/apiclick.aspx?...&url=<encoded>`), which `unwrap_bing()` in `plan-2.md` undoes.

## X posts (Task 7)
X has no keyless feed. Profile timelines (`syndication.twitter.com/srv/timeline-profile/...`) answer HTTP
429, every Nitter mirror is down or blocked, and RSSHub's routes are 404. Two things do work:
1. **Finding posts:** a Google News search `site:x.com/<handle>` lists the posts Google has indexed, with
   the post text as the headline. Fresh on 2 Oct for elonmusk (28 in 24 hours), sama, OpenAIDevs,
   GoogleDeepMind, sundarpichai, AnthropicAI, claudeai, karpathy and nvidia.
2. **Reading one post in full:** GET `https://cdn.syndication.twimg.com/tweet-result` with `id=<tweet id>`,
   `token=<below>`, `lang=en`, browser headers. It returned 200 with `created_at`, `text`,
   `user.screen_name`, and, where present, `quoted_tweet`, `parent`, `in_reply_to_screen_name`.
```python
def _tweet_token(tweet_id):
    x = (int(tweet_id) / 1e15) * math.pi
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    ip, fp = int(x), x - int(x)
    s = ""
    while ip:
        s = digits[ip % 36] + s
        ip //= 36
    f = ""
    for _ in range(11):
        fp *= 36
        d = int(fp)
        f += digits[d]
        fp -= d
    return re.sub(r"(0+|\.)", "", s + "." + f)
```
A Google News link to a post must be decoded first (`web_text.decode_google_news`), which `fetch_one`
already does. Decoding sometimes fails for posts indexed the same day; the headline is then all there is.

## lablab.ai (Task 6)
`https://lablab.ai/ai-hackathons` (browser User-Agent, about 800 KB) has no API and no feed. The events
sit in the page's Next.js data chunks. This returned 145 records on 2 Oct, 5 of them still open:
```python
def parse_lablab_listing(html, now):
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, flags=re.S)
    if not chunks:
        return []
    data = json.loads('"' + "".join(chunks) + '"')
    seen = {}
    for m in re.finditer(r'"endAt":"([^"]+)","startAt":"([^"]+)"', data):
        after = data[m.end(): m.end() + 1500]
        slug = re.search(r'"slug":"([a-z0-9-]+)","previousSlugs"', after)
        kind = re.search(r'"type":"([A-Z_]+)"', after)
        signup = re.search(r'"signupActive":(true|false)', data[max(0, m.start() - 300): m.start()])
        if not slug or not kind or kind.group(1) != "HACKATHON":
            continue
        end = datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
        if end > now:
            seen.setdefault(slug.group(1), {"slug": slug.group(1), "start": m.group(2)[:10],
                                            "end": m.group(1)[:10],
                                            "signup": bool(signup and signup.group(1) == "true")})
    return sorted(seen.values(), key=lambda e: e["end"])
```
Event pages (`https://lablab.ai/ai-hackathons/<slug>`) render the prize split, eligibility and deadline
as plain text, so the existing `find_opportunities.check()` reads them.

## Other hackathon platforms (Task 6)
- **Devpost** — `https://devpost.com/api/hackathons`, already used by `devpost()`. For the newest events:
  params `status[]=open`, `status[]=upcoming`, `search=AI`, `order_by=recently-added`. Fields seen: `id`,
  `title`, `displayed_location`, `open_state`, `url`, `time_left_to_submission`,
  `submission_period_dates`, `themes`, `prize_amount`, `prizes_counts`.
- **Devfolio** — POST `https://api.devfolio.co/api/search/hackathons`, JSON body
  `{"type": "application_open", "from": 0, "size": 10}`. Returns `hits` (10). First keys seen: `country`,
  `devfolio_official`, `featured`, `private`, `starts_at`, `hosted_by`, `hashtags`, `apply_mode`, `city`,
  `timezone`. The record may sit under `_source`.
- **Unstop** — GET `https://unstop.com/api/public/opportunity/search-result?opportunity=hackathons&per_page=10&oppstatus=open&searchTerm=AI`.
  Returns `data` (10). First keys seen: `id`, `public_url`, `title`, `organization_id`, `type`, `subtype`,
  `regn_open`, `updated_at`, `region`, `visibility`.

## Rejected — tested, not worth retrying
- **X, direct:** timeline endpoint (429), Nitter mirrors (xcancel 451; nitter.net, poast, privacydev
  unreachable; tiekoetter captcha; nitter.space and lightbrd 403), RSSHub (404). `site:x.com/xai` has 3
  posts, the newest from May 2026. `site:x.com/grok` is Grok's automatic replies. YouTube `@xai` has one
  video from 2022. `x.ai/news/rss.xml` and `x.ai/blog/rss.xml` are 404.
- **News feeds dead, blocked or stale:** ZDNet AI (404), Forbes AI (404), Stanford HAI and The Neuron (no
  entries), WSJ Technology (newest Jan 2026), Synced (Aug 2026), The Gradient (Feb 2026), BAIR (Jul 2026),
  OpenAI Alignment blog (Jul 2026), Hyperdimensional (1 Sep 2026), `blogs.microsoft.com/ai/feed` (410),
  Google Developers Blog (entries carry no date, so the scraper drops them all), Epoch AI atom (404),
  AI Frontiers (404), Anthropic Alignment blog (404), Apollo Research and LangChain (no entries),
  LlamaIndex (404), Make (403), HBR (SSL error), EU-Startups, Tech Funding News, FinSMEs and Euractiv
  (403), TechNode's main feed (2,000 entries; TechNode Global is used), Nikkei Asia, KED Global and PIB
  (undated), dev.to and Medium AI tags (noise).
- **India:** Analytics India Magazine, ET AI, Financial Express and CXOToday (no entries), Gadgets360 and
  NDTV Profit (403), VCCircle (500), Times of India Tech (newest Aug 2026), Moneycontrol (Apr 2026).
- **Search and social:** Yahoo News RSS (empty or 404), DuckDuckGo HTML (no dates), Bluesky profile RSS
  (empty or 404), Reddit multi-subreddit URLs (429; r/LocalLLaMA alone works until 13 Nov 2026),
  hnrss.org (502 at times; Algolia is used), Hugging Face daily papers (days behind; arXiv covers them).
- **Hackathon platforms:** `devpost.com/hackathons.rss` (406), MLH and HackClub (students only),
  HackerEarth (client-rendered), DoraHacks API (404), Kaggle (reCAPTCHA), AIcrowd (500), challenge.gov
  API (404), hackathons.io (timeout), opportunitydesk.org (too general), indiaai.gov.in feeds (404).
  Pages that load but have no parser yet, lower priority: TAIKAI, `lu.ma/ai`, Cerebral Valley,
  Eventbrite, hackathon.com.
- **Open-model feeds (rejected 2026-09-07):** `mistral.ai/news/feed.xml`, `ai.meta.com/blog/rss/`,
  `lmstudio.ai/blog/rss.xml` (404), `qwenlm.github.io` (abandoned), `papers.takara.ai` (days behind).
  `https://mistral.ai/rss.xml` does work and is in `sources.txt`.
