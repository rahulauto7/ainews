"""
Scrape every source in feed_sources.py: RSS and Atom feeds, plus the non-RSS readers in EXTRA.

Time windows (see WINDOW_HOURS / QUANTUM_SOURCES below):
  - Every news source uses a strict LAST 24 HOURS window. The scrape cuts at
    NEWS_RULE_HOURS minus BUILD_ALLOWANCE_HOURS, because the rule is measured when
    the edition is SENT, not when it is scraped.
  - Quantum sources are the one news exception: a 7-DAY rule, because the section
    is weekly and each issue covers the whole week since the last one.
  - Quantum sources are skipped entirely on non-Thursdays.
  - Opportunity sources are the one exception: they are dated by DEADLINE, not
    by announcement, so they keep a 30-day window (see OPPORTUNITY_WINDOW_HOURS).

Articles with no parseable publish date are DROPPED, so "last 24 hours" is a real
guarantee rather than a best effort.

Outputs .tmp/rss_articles.json
"""

import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import feedparser
import requests

# Siblings import by bare name, so run_daily_pipeline.py's "tools.scrape_rss_feeds"
# needs this directory on the path, as running the file directly provides.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from feed_sources import EXTRA, RSS  # noqa: E402
from web_text import UA as BROWSER_UA  # noqa: E402

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(PROJECT_ROOT, ".tmp")
OUTPUT_FILE = os.path.join(TMP_DIR, "rss_articles.json")

# ── Sources ───────────────────────────────────────────────────────────────────
# Every source, its digest group and its flags live in feed_sources.py, which also
# lists the sources tested and rejected. The sets below are derived from it.
FEEDS = {name: url for name, url, _category, _flags in RSS}
CATEGORY = {name: category for name, _url, category, _flags in RSS}
CATEGORY.update({name: category for name, category, _kind, _arg in EXTRA})
AI_FILTER_SOURCES = {name for name, _u, _c, flags in RSS if "ai" in flags.split()}
MUSK_FILTER_SOURCES = {name for name, _u, _c, flags in RSS if "musk" in flags.split()}
BROWSER_UA_SOURCES = {name for name, _u, _c, flags in RSS if "browser" in flags.split()}
TOP_SOURCES = {name for name, _u, _c, flags in RSS if "top" in flags.split()}


# arXiv feeds return hundreds of papers — limit to most relevant
ARXIV_MAX_PER_FEED = 15
# Sources flagged "top" (the regional Google News editions, 100 results each)
# keep only their first entries, which Google ranks as the most prominent.
TOP_PER_FEED = 20

# ── Time Windows ──────────────────────────────────────────────────────────────
# Strict last 24 hours for every news source, quantum included.
#
# NEWS_RULE_HOURS is the promise to the reader: nothing older than this in the
# inbox. It is measured at SEND, which is why the scrape window is deliberately
# SHORTER than the rule.
#
# The gap matters. A scrape cutting at a full 24h hands the curator articles that
# are already 24h old, and every minute spent curating, rendering and mailing
# pushes them past the rule. On 2026-09-17 the scrape ran at 00:04 UTC and the
# edition was mailed at 15:39 UTC: 34 of 44 news stories arrived over 24h old,
# although the scrape-side window had been correct all along. Reserving the
# build allowance up front is what makes the rule survive the pipeline.
#
# Quantum is the one news exception, and a deliberate one: the section runs
# WEEKLY (Thursdays), so each issue has to cover the whole week since the last
# one. A 24h rule would leave it empty or near-empty every Thursday. It is a
# wider rule, not an absent one - a quantum story over 7 days old is still
# stale and still blocks the send. Everything else is 24h, no exceptions.
NEWS_RULE_HOURS = 24
QUANTUM_RULE_HOURS = 24 * 7
BUILD_ALLOWANCE_HOURS = 2      # curate + render + verify + send must fit in here
DEFAULT_WINDOW_HOURS = NEWS_RULE_HOURS - BUILD_ALLOWANCE_HOURS
QUANTUM_WINDOW_HOURS = QUANTUM_RULE_HOURS - BUILD_ALLOWANCE_HOURS
# Opportunities are dated by their DEADLINE, not by when they were announced, so a
# 24h window loses almost all of them. On 2026-09-07 the opportunity section was
# empty for exactly this reason: not one of the 176 articles scraped that day was a
# hackathon, contest or programme, because the announcements were all older than a
# day while the entry windows were still open.
OPPORTUNITY_WINDOW_HOURS = 24 * 30

QUANTUM_SOURCES = {name for name, category in CATEGORY.items() if category == "quantum"}
OPPORTUNITY_SOURCES = {name for name, category in CATEGORY.items() if category == "opportunity"}

# Monday=0 ... Thursday=3. Quantum sources are only scraped on this weekday.
# Opportunity sources have no such restriction - they run every day.
QUANTUM_WEEKDAY = 3


def window_hours_for(source_name):
    """Return the lookback window, in hours, for a given feed."""
    if source_name in QUANTUM_SOURCES:
        return QUANTUM_WINDOW_HOURS
    if source_name in OPPORTUNITY_SOURCES:
        return OPPORTUNITY_WINDOW_HOURS
    return DEFAULT_WINDOW_HOURS


# ── Opportunity Qualification Gate ────────────────────────────────────────────
# The opportunity section is for things the reader can ENTER or APPLY TO. A story
# qualifies only if it names an AI subject AND an entry mechanism - both, not
# either. Requiring both is what keeps the section clean: a Product Hunt launch
# and an arXiv paper are about AI but have nothing to enter, while a marathon
# registration has an entry mechanism but nothing to do with AI. Each is rejected
# by the half it fails.

_AI_TERMS = re.compile(
    r"\b(ai|a\.i\.|artificial intelligence|machine learning|deep learning|"
    r"generative|genai|gen ai|llm|large language model|neural|data science|"
    r"robotics|computer vision|nlp|agentic|agents?)\b",
    re.I,
)

# Strong terms are entry mechanisms and nothing else - a headline containing one
# is an opportunity on its own evidence.
_OPPORTUNITY_STRONG = re.compile(
    r"\b(hackathon|hack-a-thon|datathon|codefest|accelerator|incubator|"
    # "IndiaAI Startups Global: International Acceleration Programs" - the real
    # example this section was rebuilt for - says "acceleration programme", never
    # "accelerator", and government schemes usually phrase it that way.
    r"accelerat(or|ion) program(me)?s?|startup program(me)?s?|"
    r"fellowship|residency|bootcamp|cohort|scholarship|"
    r"call for (applications|proposals|entries|submissions)|"
    r"applications? (open|are open|now open|invited|close)|apply now|"
    r"submissions? open|registration (open|is open)|pitch (competition|contest))\b",
    re.I,
)

# Weak terms have an ordinary English sense that has nothing to do with entering
# anything: "models CHALLENGE frontier systems", "AI COMPETITION heats up between
# Google and OpenAI", "the GRANT of a licence". Each needs corroboration below.
_OPPORTUNITY_WEAK = re.compile(
    r"\b(competition|contest|challenge|grant|prizes?|awards?)\b",
    re.I,
)

# What turns a weak term into a real one: evidence that somebody can enter it.
_ENTRY_SIGNALS = re.compile(
    r"(\$[\d,]+|₹[\d,]+|\b(prize|prizes|stipend|deadline|apply|applies|"
    r"applications?|submission|submissions|submit|register|registration|"
    r"entries|entrants|eligib\w+|winners will|launch(es|ed|ing)?|opens?|"
    r"invites?|seeking|call for)\b)",
    re.I,
)

# Rejected even when both gates pass. These describe an opportunity being WON,
# JUDGED or CLOSED - there is nothing left for the reader to enter.
_CLOSED_TERMS = re.compile(
    r"\b(winners? (announced|named|revealed|crowned)|"
    # Up to two words may sit between the verb and the noun: "wins the AI
    # hackathon", "won this year's data challenge".
    r"(wins?|won) (the |this |their )?(\w+[' ]?s? )?(\w+ )?(hackathon|competition|challenge|award|prize)|"
    r"top (award|prize|honou?rs)|earns? top|crowned|runner-?up|"
    r"applications? (close[d]?|have closed)|deadline (has )?passed)\b",
    re.I,
)


def qualifies_as_opportunity(title, summary=""):
    """True if this is something a reader can still enter or apply to.

    Checked against the TITLE first; the summary is only consulted for the AI
    half, because Google News summaries carry outlet boilerplate that trips the
    opportunity terms far too easily.
    """
    title = title or ""
    if _CLOSED_TERMS.search(title):
        return False

    if _OPPORTUNITY_STRONG.search(title):
        pass
    elif _OPPORTUNITY_WEAK.search(title) and _ENTRY_SIGNALS.search(title):
        pass
    else:
        return False

    return bool(_AI_TERMS.search(title) or _AI_TERMS.search(summary or ""))


# ── Relevance filters and link clean-up ──────────────────────────────────────
# Sources flagged "ai" in feed_sources.py are general-interest feeds (BBC, Inc42,
# Ars Technica): only their AI stories are kept. Sources flagged "musk" (Teslarati,
# Electrek) keep only stories where Musk talks about AI, autonomy or the hardware
# behind them; his pay package or Tesla's delivery numbers are not that.

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


def _bing_publisher(entry):
    """The outlet a Bing News item came from. Bing's RSS carries it as <News:Source>,
    which feedparser exposes as news_source; not yet seen on a live feed (2026-10-02)."""
    source = entry.get("news_source") or (entry.get("source") or {}).get("title")
    return " ".join(str(source).split()) if source else ""


SUMMARY_MAX_CHARS = 1500


def plain_summary(raw):
    """Feed summary as plain text, tags stripped BEFORE it is cut to length.

    The raw HTML used to be sliced to 500 characters first. The Decoder, Wired
    and many r/LocalLLaMA posts open with an <img> tag that used most of that
    budget, so ~100 characters of text survived ("The group without AI" was
    all that was left of one Decoder story, 2026-09-14), and the agent had to
    fetch or search for every such story.
    """
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))
    text = re.sub("[\u200b-\u200d\u2060\ufeff]", "", text)
    return " ".join(text.split())[:SUMMARY_MAX_CHARS]


def title_from_text(text, limit=110):
    """A headline for an untitled post: its first sentence, cut between words."""
    text = " ".join((text or "").split())
    if not text:
        return ""
    first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    if len(first) <= limit:
        return first
    return first[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-") + "..."


def articles_from_feed(name, feed, cutoff_time):
    """Articles from a parsed feed: dated, inside the window, and past the source's filters.

    Pure, so a test can pass feedparser.parse(xml_text).
    """
    is_arxiv = name.startswith("arXiv")
    is_bing = "(via Bing News)" in name
    cap = ARXIV_MAX_PER_FEED if is_arxiv else TOP_PER_FEED if name in TOP_SOURCES else MAX_PER_FEED
    articles = []
    undated = 0
    for entry in feed.entries:
        # Parse published date
        published = None
        for date_field in ("published_parsed", "updated_parsed", "created_parsed"):
            parsed_time = getattr(entry, date_field, None)
            if parsed_time:
                published = datetime(*parsed_time[:6], tzinfo=timezone.utc)
                break

        # Drop anything we cannot date. Previously undated entries were kept
        # ("better to over-include"), but the digest now promises a strict
        # window, and an undated article cannot be shown to be inside it.
        if published is None:
            undated += 1
            continue
        if published < cutoff_time:
            continue

        summary = plain_summary(getattr(entry, "summary", getattr(entry, "description", "")))
        # Bluesky and Mastodon posts carry no title, so the post's opening words stand in.
        title = getattr(entry, "title", None) or title_from_text(summary) or "No title"
        if name in AI_FILTER_SOURCES and not mentions_ai(title, summary):
            continue
        if name in MUSK_FILTER_SOURCES and not musk_on_ai(title, summary):
            continue

        article = {
            "title": title,
            "url": unwrap_bing(getattr(entry, "link", "")),
            "source": name,
            "published": published.isoformat(),
            "published_date": published.strftime("%Y-%m-%d"),
            "summary": summary,
            "category": _categorize_source(name),
        }
        # The PDF names the outlet, not "via Bing News" (builder_helpers.S()).
        if is_bing and _bing_publisher(entry):
            article["publisher"] = _bing_publisher(entry)
        # Opportunity feeds are noisy by design (broad queries, wide window),
        # so every entry carries the gate's verdict and the curation step can
        # filter on a field rather than re-deriving the rule.
        if name in OPPORTUNITY_SOURCES:
            article["is_opportunity"] = qualifies_as_opportunity(
                article["title"], article["summary"]
            )
        articles.append(article)

        # Cap every feed; arXiv hardest, since it returns hundreds of papers.
        if len(articles) >= cap:
            break

    if undated:
        print(f"  [DROPPED {undated} undated] {name}")
    return articles


# A refusal worth one more try: Google News answers 503 and Reddit 429 to a burst
# from the bot User-Agent, and both answer the browser one a moment later.
RETRY_STATUSES = {403, 429, 503}


def fetch_feed(name, url, cutoff_time, timeout=20):
    """Fetch and parse a single RSS feed. Returns list of articles."""
    ua = BROWSER_UA if name in BROWSER_UA_SOURCES else BOT_UA
    try:
        response = requests.get(url, timeout=timeout, headers={"User-Agent": ua})
        if response.status_code in RETRY_STATUSES:
            time.sleep(2)
            response = requests.get(url, timeout=timeout, headers={"User-Agent": BROWSER_UA})
        response.raise_for_status()
        return articles_from_feed(name, feedparser.parse(response.content), cutoff_time)
    except requests.exceptions.Timeout:
        print(f"  [TIMEOUT] {name} ({url})")
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] {name}: {e}")
    except Exception as e:
        print(f"  [PARSE ERROR] {name}: {e}")
    return []


# ── Non-RSS readers (EXTRA in feed_sources.py) ────────────────────────────────
# Each reader takes (name, arg, cutoff_time) and returns the same article dicts as
# articles_from_feed. On any error it prints one line and returns [], so one broken
# page never stops the scrape. Parsing sits in pure functions for offline tests.

_REL = re.compile(r"(\d+)\s*(minutes?|mins?|m|hours?|hrs?|h)\b", re.I)


def relative_to_datetime(text, now):
    """'13h ago' covers 13:00-13:59 ago, so the older bound is used. Days and months return None."""
    m = _REL.search(text or "")
    if not m:
        return None
    n = int(m.group(1)) + 1
    return now - (timedelta(minutes=n) if m.group(2).lower().startswith("m") else timedelta(hours=n))


def _article(name, title, url, published, summary, source=None):
    return {
        "title": title,
        "url": url,
        "source": source or name,
        "published": published.isoformat(),
        "published_date": published.strftime("%Y-%m-%d"),
        "summary": summary,
        "category": _categorize_source(name),
    }


def parse_hn(js, name, cutoff_time):
    """Hacker News stories (Algolia search JSON) inside the window that are about AI."""
    out = []
    for hit in js.get("hits") or []:
        title = hit.get("title") or ""
        created = hit.get("created_at_i")
        if not title or not created or not mentions_ai(title):
            continue
        published = datetime.fromtimestamp(int(created), tz=timezone.utc)
        if published < cutoff_time:
            continue
        thread = f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        summary = (f"{hit.get('points', 0)} points and {hit.get('num_comments', 0)} comments "
                   f"on Hacker News. Discussion: {thread}")
        out.append(_article(name, title, hit.get("url") or thread, published, summary))
    return out


def read_hn(name, _arg, cutoff_time):
    try:
        r = requests.get("https://hn.algolia.com/api/v1/search", timeout=20, params={
            "tags": "story",
            "numericFilters": f"created_at_i>{int(cutoff_time.timestamp())},points>80",
            "hitsPerPage": 60,
        }, headers={"User-Agent": BOT_UA})
        r.raise_for_status()
        return parse_hn(r.json(), name, cutoff_time)
    except Exception as e:  # noqa: BLE001 - one reader must never stop the scrape
        print(f"  [ERROR] {name}: {e}")
        return []


def parse_hf_models(items, name, cutoff_time):
    """Hugging Face models created inside the window, from the likes7d listing."""
    out = []
    for item in items or []:
        model_id, created = item.get("id"), item.get("createdAt")
        if not model_id or not created:
            continue
        published = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if published < cutoff_time:
            continue
        summary = (f"{model_id} was published on Hugging Face and drew {item.get('likes', 0)} likes "
                   f"and {item.get('downloads', 0)} downloads in its first days.")
        out.append(_article(name, f"New on Hugging Face: {model_id}",
                            f"https://huggingface.co/{model_id}", published, summary))
    return out


def read_hf_models(name, _arg, cutoff_time):
    try:
        r = requests.get("https://huggingface.co/api/models", timeout=20, params={
            "sort": "likes7d", "direction": -1, "limit": 100,
        }, headers={"User-Agent": BOT_UA})
        r.raise_for_status()
        return parse_hf_models(r.json(), name, cutoff_time)
    except Exception as e:  # noqa: BLE001
        print(f"  [ERROR] {name}: {e}")
        return []


def _video_renderers(node):
    if isinstance(node, dict):
        if "videoRenderer" in node:
            yield node["videoRenderer"]
        for value in node.values():
            yield from _video_renderers(value)
    elif isinstance(node, list):
        for value in node:
            yield from _video_renderers(value)


def parse_yt_search(page, name, cutoff_time, now):
    """Videos from a YouTube search results page, dated from their relative upload time."""
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", page or "", re.S)
    if not m:
        return []
    out, seen = [], set()
    for v in _video_renderers(json.loads(m.group(1))):
        vid = v.get("videoId")
        title = "".join(r.get("text", "") for r in (v.get("title") or {}).get("runs", []))
        published = relative_to_datetime((v.get("publishedTimeText") or {}).get("simpleText"), now)
        if not vid or vid in seen or not title or published is None or published < cutoff_time:
            continue
        seen.add(vid)
        channel = ((v.get("ownerText") or {}).get("runs") or [{}])[0].get("text", "")
        out.append(_article(name, title, f"https://www.youtube.com/watch?v={vid}", published,
                            f"YouTube video by {channel or 'an unknown channel'}.",
                            source=f"{channel} (YouTube)" if channel else name))
    return out


def read_yt_search(name, query, cutoff_time):
    try:
        r = requests.get("https://www.youtube.com/results", timeout=20, params={
            "search_query": query, "sp": "CAISBAgCEAE=",  # videos, uploaded today, newest first
        }, headers={"User-Agent": BROWSER_UA, "Accept-Language": "en-US,en;q=0.9"})
        r.raise_for_status()
        return parse_yt_search(r.text, name, cutoff_time, datetime.now(timezone.utc))
    except Exception as e:  # noqa: BLE001
        print(f"  [ERROR] {name}: {e}")
        return []


EXTRA_READERS = {"hn": read_hn, "hf_models": read_hf_models, "yt_search": read_yt_search}


# ── Company routing ───────────────────────────────────────────────────────────
# A story about OpenAI must reach the OpenAI group of the digest even when the copy
# that survives de-duplication came from The Verge. Only pooled groups are routed:
# an Indian outlet's OpenAI story stays Indian.

POOL_CATEGORIES = {"general", "company_blog", "video", "social", "showcase"}
CATEGORY_PRIORITY = ["opportunity", "quantum", "elon_musk", "xai_grok", "openai", "anthropic_claude",
                     "google", "open_model", "closed_model", "indian", "rsi", "problems",
                     "automation", "business", "world", "world_lang"]
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


# ── Same-story Deduplication ──────────────────────────────────────────────────
# URL dedupe alone is not enough: a single story is syndicated under different
# headlines by many outlets. On 2026-09-03 the Andhra Pradesh quantum-AI
# university appeared 6 times and one Anthropic story 5 times, each with a
# distinct URL. We cluster on significant headline tokens instead.

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with", "at",
    "by", "from", "as", "is", "are", "was", "were", "be", "been", "it", "its",
    "that", "this", "these", "new", "says", "say", "said", "how", "why", "what",
    "will", "can", "could", "would", "after", "over", "into", "out", "up",
    "down", "not", "but", "has", "have", "had", "get", "gets", "amid", "via",
    "first", "1st", "now", "more", "than", "his", "her", "their",
}

# Spelling and numeral variants that would otherwise split one cluster.
_SYNONYMS = {
    "1st": "first", "artificialintelligence": "ai",
    "amaravathi": "amaravati", "ap": "andhrapradesh",
    "varsity": "university", "country": "india", "countrys": "india",
}


def title_tokens(title):
    """Significant-token set for a headline, publisher suffix stripped."""
    base = title.split(" - ")[0]
    base = unicodedata.normalize("NFKD", base)
    # Normalise curly apostrophes and drop possessive endings BEFORE the ascii
    # strip below, which deletes the apostrophe outright. Otherwise "India's"
    # tokenises to "indias" and never matches a plain "india".
    base = base.replace("’", "'").replace("‘", "'")
    base = re.sub(r"'s\b", "", base)
    base = base.encode("ascii", "ignore").decode()
    tokens = set()
    for word in re.findall(r"[a-z0-9]+", base.lower()):
        word = _SYNONYMS.get(word, word)
        if word in _STOPWORDS or len(word) < 3:
            continue
        tokens.add(word)
    return tokens


def _same_story(a_tokens, b_tokens, threshold=0.5):
    """True when two headlines describe the same story.

    Overlap is scored against the SHORTER headline, so a terse wire headline
    still matches a longer descriptive one.
    """
    if not a_tokens or not b_tokens:
        return False
    shared = len(a_tokens & b_tokens)
    return shared >= 3 and shared / min(len(a_tokens), len(b_tokens)) >= threshold


def _representative(members):
    """Pick which copy of a story to keep.

    Prefers a real publisher feed over a Google News or Bing News proxy, then the
    entry with the most summary text, since proxy entries carry only the headline.
    A forum post (Reddit, Bluesky) comes last: it is talk about a story, and the
    outlet that reported it is the copy worth keeping.
    """
    def rank(a):
        source = a.get("source", "")
        is_proxy = "via Google News" in source or "via Bing News" in source
        return (a.get("category") == "forums", is_proxy, -len(a.get("summary") or ""))
    return sorted(members, key=rank)[0]


def _title_clustered(article):
    """False for sources whose titles must not be clustered.

    Syndication is a NEWS phenomenon - the same press release rewritten by many
    outlets. arXiv papers are never syndicated, and papers within one subfield
    share so much vocabulary that title similarity produces false merges ("Codes
    for Quantum Secret Sharing with a Helper" vs "Quantum Secret Sharing with a
    Helper and Programmable Access Structures" are two different papers, 0.8
    token overlap). Hugging Face items are all titled "New on Hugging Face: <id>",
    so two models from one org already share three tokens. Non-English headlines
    (world_lang) all carry their language's words for "artificial intelligence"
    - Vietnamese "tri tue nhan tao" is four tokens once the accents go - so they
    merged with each other on the first run (2026-10-03); a shared link still
    de-duplicates them.
    """
    source = article.get("source", "")
    return not (source.startswith("arXiv") or source == "Hugging Face new models"
                or article.get("category") == "world_lang")


MAX_ALTERNATES = 6


def deduplicate_stories(articles):
    """Collapse duplicates: the same URL, or the same story under other headlines.

    Returns (kept, removed_count). Copies of one URL join one cluster before any
    copy is dropped, so the group they arrived under still counts: Google News
    gives an article the same link in every query that finds it, and the copy
    from the first query in the registry used to win outright, whatever its group.
    """
    clusters = []  # [(tokens, [articles])]; tokens None for an unclustered source
    by_url = {}
    for article in articles:
        url = article.get("url")
        if url and url in by_url:
            by_url[url].append(article)
            continue
        if not _title_clustered(article):
            members = [article]
            clusters.append((None, members))
        else:
            tokens = title_tokens(article.get("title", ""))
            for cluster_tokens, members in clusters:
                if cluster_tokens is not None and _same_story(tokens, cluster_tokens):
                    members.append(article)
                    break
            else:
                members = [article]
                clusters.append((tokens, members))
        if url:
            by_url[url] = members

    kept = []
    for _, members in clusters:
        # A copy from an opportunity feed counts only if it passed the gate, or real
        # news would be hidden with it. Such a copy is not kept either while another
        # exists: it can be 30 days old and would carry its date into a 24h group.
        counted = [m for m in members
                   if m.get("category") != "opportunity" or m.get("is_opportunity")]
        best = _representative(counted or members)
        # The kept copy takes the most specific group any counted copy arrived under.
        cats = {m.get("category", "general") for m in counted}
        specific = [c for c in CATEGORY_PRIORITY if c in cats]
        if specific:
            best["category"] = specific[0]
            if specific[0] == "opportunity":
                best["is_opportunity"] = True
            if len(specific) > 1:
                best["also_in"] = specific[1:]
        # Corroboration is a useful relevance signal, so keep the trail. A second
        # search that found the same link is not a second outlet, so it counts once.
        others = [m for m in members if m.get("url") != best.get("url")]
        if others:
            best["also_reported_by"] = sorted({m["source"] for m in others})
            best["duplicate_count"] = len({m.get("url") for m in members})
            # The other outlets' own links, so fetch_articles.py can read the story
            # elsewhere when this publisher blocks the fetch or shows a paywall.
            alternates, seen = [], {best.get("url")}
            for m in sorted(others, key=lambda a: "via Google News" in a.get("source", "")):
                if m.get("url") and m["url"] not in seen and len(alternates) < MAX_ALTERNATES:
                    seen.add(m["url"])
                    alternates.append({"source": m["source"], "url": m["url"], "title": m["title"]})
            best["alternates"] = alternates
        kept.append(best)

    return kept, len(articles) - len(kept)


def _categorize_source(source_name):
    """The digest group a source feeds, from the registry."""
    return CATEGORY.get(source_name, "general")


def _fetch_host(jobs, now):
    """One host's feeds, in turn and politely. Returns [(name, articles)]."""
    out = []
    for name, url in jobs:
        out.append((name, fetch_feed(name, url, now - timedelta(hours=window_hours_for(name)))))
        time.sleep(0.6)
    return out


def scrape_all_feeds():
    """Scrape every registered source and save to JSON."""
    os.makedirs(TMP_DIR, exist_ok=True)

    now = datetime.now(timezone.utc)
    is_quantum_day = now.weekday() == QUANTUM_WEEKDAY
    all_articles = []

    print(f"Scraping RSS feeds at {now.strftime('%Y-%m-%d %H:%M UTC')} ({now.strftime('%A')})")
    print(f"  default window : last {DEFAULT_WINDOW_HOURS}h")
    print(f"  quantum window : last {QUANTUM_WINDOW_HOURS}h "
          f"({'INCLUDED - quantum day' if is_quantum_day else 'SKIPPED - not Thursday'})")

    # Hosts in parallel, the feeds of one host in turn and politely. The Google
    # News searches share one host, so they run one after another.
    hosts = {}
    for name, url in FEEDS.items():
        if name in QUANTUM_SOURCES and not is_quantum_day:
            continue
        hosts.setdefault(urllib.parse.urlparse(url).netloc, []).append((name, url))
    results = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        readers = {name: ex.submit(EXTRA_READERS[kind], name, arg,
                                   now - timedelta(hours=window_hours_for(name)))
                   for name, _category, kind, arg in EXTRA}
        for batch in ex.map(lambda jobs: _fetch_host(jobs, now), hosts.values()):
            results.update(batch)
        for name, future in readers.items():
            results[name] = future.result()

    # One line per source, in registry order.
    for name in list(FEEDS) + [e[0] for e in EXTRA]:
        if name not in results:
            print(f"  [ skipped   ] {name} (quantum runs Thursdays)")
            continue
        articles = results[name]
        w = window_hours_for(name)
        tag = f"{w // 24}d" if w >= 48 else f"{w}h"
        if name in OPPORTUNITY_SOURCES:
            kept = sum(1 for a in articles if a.get("is_opportunity"))
            tag += f", {kept}/{len(articles)} pass gate"
        print(f"  [{len(articles):>3} articles] {name}  ({tag})")
        all_articles.extend(route_by_title(a) for a in articles)

    empty = [name for name, articles in results.items() if not articles]
    print(f"\nSources: {len(results)} read, {len(results) - len(empty)} returned articles")
    print(f"  none from: {', '.join(empty) if empty else '-'}")

    # Collapse the same URL, and the same story reported by multiple outlets.
    # An article with no link cannot be printed or fetched.
    unique_articles = [a for a in all_articles if a["url"]]
    unique_articles, dup_removed = deduplicate_stories(unique_articles)
    print(f"Dedupe: removed {dup_removed} duplicate reports (same link or same story)")

    # Sort by date (newest first)
    unique_articles.sort(
        key=lambda a: a.get("published") or "1970-01-01",
        reverse=True
    )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "scraped_at": now.isoformat(),
            "cutoff": (now - timedelta(hours=DEFAULT_WINDOW_HOURS)).isoformat(),
            "quantum_cutoff": (now - timedelta(hours=QUANTUM_WINDOW_HOURS)).isoformat()
                              if is_quantum_day else None,
            "default_window_hours": DEFAULT_WINDOW_HOURS,
            "quantum_window_hours": QUANTUM_WINDOW_HOURS,
            "opportunity_window_hours": OPPORTUNITY_WINDOW_HOURS,
            "opportunity_cutoff": (now - timedelta(hours=OPPORTUNITY_WINDOW_HOURS)).isoformat(),
            "opportunities_passing_gate": sum(
                1 for a in unique_articles if a.get("is_opportunity")
            ),
            "quantum_day": is_quantum_day,
            "total_articles": len(unique_articles),
            "duplicates_removed": dup_removed,
            "sources_scraped": len(results),
            "articles": unique_articles,
        }, f, indent=2, ensure_ascii=False)

    print(f"\nDone! {len(unique_articles)} unique articles saved to {OUTPUT_FILE}")
    return unique_articles


if __name__ == "__main__":
    scrape_all_feeds()
