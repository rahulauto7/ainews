# Plan part 2 — scraper and digest

CURRENT · written Fri 2 Oct 2026 · nothing below is implemented yet · follows `plan-1.md`.

## Task 4 — scraper: relevance filter, company routing, parallel fetch
**Files:** `tools/scrape_rss_feeds.py`, `tools/builder_helpers.py` (`S()`, line 97), `tools/prep_run.py`
line 124, more cases in `tools/tests/test_sources.py`.
New imports in the scraper: `urllib.parse`, `from concurrent.futures import ThreadPoolExecutor`.

**4a. Filters and link clean-up** — add beside the opportunity gate:
```python
BOT_UA = "GlobalAINews/1.0 (RSS Reader)"
MAX_PER_FEED = 60

_AI_NEWS = re.compile(
    r"\b(a\.?i\.?|artificial intelligence|machine learning|deep learning|neural net\w*|generative|"
    r"genai|llms?|large language models?|chatbots?|agentic|ai agents?|superintelligence|agi|openai|"
    r"chatgpt|gpt-?\d[\w.]*|anthropic|claude|gemini|deepmind|copilot|llama|mistral|deepseek|qwen|"
    r"grok|xai|hugging ?face|humanoid|robotaxi|self-driving)\b", re.I)
_MUSK = re.compile(r"\b(elon|musk)\b", re.I)
_MUSK_AI = re.compile(
    r"\b(fsd|full self-driving|autopilot|optimus|dojo|neuralink|autonomy|autonomous|compute|chips?)\b", re.I)


def mentions_ai(title, summary=""):
    """True when a general-interest feed entry is about AI."""
    return bool(_AI_NEWS.search(title or "") or _AI_NEWS.search(summary or ""))


def musk_on_ai(title, summary=""):
    """True when the entry has Musk talking about AI, autonomy or the hardware behind them."""
    text = f"{title or ''} {summary or ''}"
    return bool(_MUSK.search(text) and (_AI_NEWS.search(text) or _MUSK_AI.search(text)))


def unwrap_bing(link):
    """Publisher URL from a Bing News click-tracking link; any other link passes through."""
    if "bing.com/news/apiclick" not in (link or ""):
        return link
    target = urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("url")
    return target[0] if target else link
```

**4b. `fetch_feed()` (line 281)** — keep the HTTP call and its three `except` branches; move the entry
loop into a pure `articles_from_feed(name, feed, cutoff_time)` so a test can pass
`feedparser.parse(xml_text)`. Send the browser User-Agent (same string as `web_text.UA`) when
`name in BROWSER_UA_SOURCES`, else `BOT_UA`; timeout 20. In the loop, after the cutoff check:
- `url = unwrap_bing(getattr(entry, "link", ""))`
- skip the entry when `name in AI_FILTER_SOURCES and not mentions_ai(title, summary)`, or when
  `name in MUSK_FILTER_SOURCES and not musk_on_ai(title, summary)`
- stop at `MAX_PER_FEED` entries (arXiv keeps `ARXIV_MAX_PER_FEED = 15`)
- Bing rows only: store the outlet as `article["publisher"]`. Print one entry's keys first to find the
  field (`news_source` is expected; this was not checked on 2 Oct). In `builder_helpers.S()` use
  `source or a.get("publisher") or a["source"]`, so the PDF names the outlet and not "via Bing News".

Everything else in the loop stays: undated entries dropped and counted, the opportunity-gate verdict.

**4c. Company routing and category inheritance** — a story about OpenAI must show up in the OpenAI group
of the digest even when the copy that survives de-duplication came from The Verge:
```python
POOL_CATEGORIES = {"general", "company_blog", "video", "social", "showcase"}
CATEGORY_PRIORITY = ["opportunity", "quantum", "elon_musk", "xai_grok", "openai", "anthropic_claude",
                     "google", "open_model", "closed_model", "indian", "rsi", "problems",
                     "automation", "business", "world"]
_ROUTES = [  # first match wins; Google is last because its name appears in other companies' stories
    ("elon_musk", re.compile(r"\b(elon|musk)\b", re.I)),
    ("xai_grok", re.compile(r"\b(xai|grok|spacexai)\b", re.I)),
    ("openai", re.compile(r"\b(openai|chatgpt|altman|gpt-?\d[\w.]*|sora|codex)\b", re.I)),
    ("anthropic_claude", re.compile(r"\b(anthropic|claude|amodei)\b", re.I)),
    ("google", re.compile(r"\b(google|gemini|deepmind|alphabet|pichai|hassabis)\b", re.I)),
]


def route_by_title(article):
    """Move a pooled article into a company's group when its headline names that company."""
    if article.get("category") in POOL_CATEGORIES:
        for category, pattern in _ROUTES:
            if pattern.search(article.get("title", "")):
                article["category"] = category
                break
    return article
```
In `deduplicate_stories()` (line 412), right after `best = _representative(members)`:
```python
        # The kept copy takes the most specific group any copy arrived under. A copy from an
        # opportunity feed counts only if it passed the gate, or real news would be hidden with it.
        cats = {m.get("category", "general") for m in members
                if m.get("category") != "opportunity" or m.get("is_opportunity")}
        specific = [c for c in CATEGORY_PRIORITY if c in cats]
        if specific:
            best["category"] = specific[0]
            if specific[0] == "opportunity":
                best["is_opportunity"] = True
            if len(specific) > 1:
                best["also_in"] = specific[1:]
```
`_representative()` (line 400): treat both `"via Google News"` and `"via Bing News"` sources as proxies.

**4d. `scrape_all_feeds()` (line 479)** — hosts in parallel, the feeds of one host in turn:
```python
def _fetch_host(jobs, now):
    """One host's feeds, in turn and politely. Returns [(name, articles)]."""
    out = []
    for name, url in jobs:
        out.append((name, fetch_feed(name, url, now - timedelta(hours=window_hours_for(name)))))
        time.sleep(0.6)
    return out

    # inside scrape_all_feeds(), replacing the sequential loop:
    hosts = {}
    for name, url in FEEDS.items():
        if name in QUANTUM_SOURCES and not is_quantum_day:
            continue
        hosts.setdefault(urllib.parse.urlparse(url).netloc, []).append((name, url))
    results = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for batch in ex.map(lambda jobs: _fetch_host(jobs, now), hosts.values()):
            results.update(batch)
    for name, _category, kind, arg in EXTRA:
        cutoff = now - timedelta(hours=window_hours_for(name))
        results[name] = EXTRA_READERS[kind](name, arg, cutoff)   # readers: handoff/recipes.md
```
Then as today: per-source log lines in registry order, `route_by_title()` on every article, URL
de-duplication, `deduplicate_stories()`, sort, write. Before the `Same-story dedupe:` line print
`Sources: N read, M returned articles` and `  none from: a, b, c` (Task 9 prunes from that line). Keep
`Done! ...` as the last line, because `prep_run.py` prints the last two. Set `"sources_scraped": len(results)`.
About 45 of the sources are Google News searches; they share one host, so they run in turn (about a minute).
`prep_run.py` line 124: print `{len(FEEDS) + len(EXTRA)} sources` instead of `34 feeds`.

**More `test_sources.py` cases** (all offline)
| What | Input | Expected |
|---|---|---|
| `mentions_ai` true | "OpenAI ships GPT-6.1 Sol"; "Why A.I. agents fail"; "A new LLM tops the benchmark" | True |
| `mentions_ai` false | "Nothing Phone (4a) gets a sale date"; "Tesla deliveries fell 2%"; "Real estate agents brace for a rate cut" | False |
| `musk_on_ai` true | "Elon Musk says FSD will be unsupervised this year"; "Musk: Grok 5 has a shot at AGI" | True |
| `musk_on_ai` false | "Tesla deliveries beat Wall Street guesses"; "Elon Musk's pay package goes to a vote" | False |
| `articles_from_feed` | inline RSS, two items dated one hour ago: an AI headline and a phone launch | as "BBC Technology" (flag ai) 1 kept; as "The Verge AI" 2 kept |
| `unwrap_bing` | `http://www.bing.com/news/apiclick.aspx?ref=FexRss&aid=&tid=abc&url=https%3a%2f%2fexample.com%2fstory&c=1` | `https://example.com/story`; a plain URL comes back unchanged |
| `route_by_title` | general "OpenAI fires three safety researchers"; general "Anthropic signs Google cloud deal"; indian "OpenAI opens Bengaluru office" | openai; anthropic_claude; stays indian |
| inheritance | one headline twice: a publisher copy (general, long summary) and a proxy copy (source "OpenAI (via Google News)", category openai) | one kept, the publisher's, with category "openai" |
| inheritance | a fresh news copy plus an opportunity-feed copy with `is_opportunity` False | category is not "opportunity" |

## Task 5 — digest: grouped in section order, capped per group
**Files:** `tools/news_digest.py` (lines 40-64, 74-82, 144-169), new `tools/tests/test_digest.py`.

`CATEGORY_ORDER` (line 40) becomes the list below. It is also the category-to-section map.
```python
CATEGORY_ORDER = [
    ("opportunity", "Opportunity feeds -> AI Hackathons / AI Grants, Fellowships & Programs"),
    ("rsi", "Self-improvement, safety, alignment -> AI Self-Improvement (RSI)"),
    ("ai_research", "Research: arXiv titles, lab and university feeds -> AI Self-Improvement (RSI)"),
    ("quantum", "Quantum, Thursdays -> Quantum + AI"),
    ("problems", "AI failures and gaps -> Unaddressed AI Problems"),
    ("automation", "Automation, agents, enterprise AI -> AI Automation & Business"),
    ("business", "Funding, startups, markets -> AI Business Opportunities"),
    ("showcase", "Product Hunt -> AI Business Opportunities"),
    ("indian", "Indian publishers -> Indian AI Industry"),
    ("world", "China, Europe, Japan, Korea, Middle East, Africa -> Global AI News"),
    ("general", "General AI news -> Global AI News"),
    ("company_blog", "Other AI companies' own blogs -> Global AI News"),
    ("openai", "OpenAI -> OpenAI"),
    ("google", "Google, Gemini, DeepMind -> Google AI"),
    ("anthropic_claude", "Anthropic and Claude -> Anthropic & Claude Code"),
    ("xai_grok", "xAI and Grok -> xAI & Grok"),
    ("open_model", "Open models -> Open Models & Open Weights"),
    ("closed_model", "Closed models -> Closed Models & Frontier APIs"),
    ("elon_musk", "Elon Musk in his own words -> Elon Musk on AI"),
    ("video", "YouTube: leads for any section"),
    ("social", "X posts, Hacker News, forums: leads for any section"),
]
```
- **Cap per group** so the digest stays near its present size (about 17k tokens today; aim to stay under
  35k): `DIGEST_CAP = 40`, with `general` 60 and `ai_research`, `video`, `social` 25. Rank inside a group
  by `duplicate_count` descending, then direct feeds before search proxies, then newest. Print the top N
  and one line `(+K more in rss_articles.json, not shown)`. Put ranking and cap in pure helpers
  (`ranked(items)`, `cap_for(category)`) so they can be tested. This limits what the curator reads, never
  how many stories a section prints.
- Replace the hand-written `SHORT_SOURCE` dict (line 53) with `short_source(name)`:
  `"… on X (via Google News)"` gives `X-<who>`; `"(via Google News)"` gives `GN-<name>`;
  `"(via Bing News)"` gives `Bing-<name>`; a name containing `YouTube` gives `YT-<name>`; anything else is
  `name[:16]`. Trim each to 18 characters.
- `snippet()` (line 76): return `""` for `"via Bing News"` sources too.
- When an article has `also_in`, append `  {also: xai_grok, closed_model}` to its line.

**`test_digest.py` cases**
1. Every category used in `feed_sources.RSS` and `EXTRA` has an entry in `CATEGORY_ORDER`. Fails today:
   the new categories are unknown.
2. Every label in `generate_pdf.SECTION_CONFIG` appears after `->` in at least one `CATEGORY_ORDER` label.
3. `ranked()`: a story carried by five outlets comes before one carried by one; at equal count a direct
   feed comes before a "via Google News" copy; at equal count and kind the newer comes first.
4. `cap_for("general") == 60`, `cap_for("openai") == 40`, `cap_for("video") == 25`.
5. `short_source("Sam Altman on X (via Google News)")` starts with `X-`;
   `short_source("OpenAI (via Bing News)")` starts with `Bing-`.
