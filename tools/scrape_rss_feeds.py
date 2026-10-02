"""
Scrape RSS feeds from 25+ AI news sources.

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
from datetime import datetime, timedelta, timezone

import feedparser
import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(PROJECT_ROOT, ".tmp")
OUTPUT_FILE = os.path.join(TMP_DIR, "rss_articles.json")

# ── RSS Feed Sources ──────────────────────────────────────────────────────────
# Organized by category for easy maintenance
FEEDS = {
    # General AI News
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "Ars Technica AI": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "MIT Technology Review": "https://www.technologyreview.com/feed/",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "The Decoder": "https://the-decoder.com/feed/",
    "AI News": "https://www.artificialintelligence-news.com/feed/",
    "Wired AI": "https://www.wired.com/feed/tag/ai/latest/rss",
    "ZDNet AI": "https://www.zdnet.com/topic/artificial-intelligence/rss.xml",
    "The Register AI": "https://www.theregister.com/software/ai_ml/headlines.atom",

    # Company Blogs
    "OpenAI Blog": "https://openai.com/blog/rss.xml",
    "Google AI Blog": "https://blog.google/technology/ai/rss/",
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",

    # Indian AI Sources
    "Inc42": "https://inc42.com/feed/",
    "YourStory": "https://yourstory.com/feed",
    "Economic Times Tech": "https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms",

    # Quantum Computing + AI  (7-day window, Thursdays only - see QUANTUM_SOURCES)
    # The arXiv RSS feed only ever carries a SINGLE day of papers (verified
    # 2026-09-03: all 143 entries shared one date), so widening the cutoff on it
    # retrieves nothing older. Real 7-day coverage comes from the Google News
    # proxy below, using the same when:Nd trick already proven on the Musk and
    # Anthropic feeds. The arXiv API (export.arxiv.org) was tried first and is
    # not usable here - it returned HTTP 429 on every attempt.
    "arXiv Quantum Physics": "https://rss.arxiv.org/rss/quant-ph",
    "Quantum + AI (via Google News)": "https://news.google.com/rss/search?q=(quantum+computing+OR+quantum+machine+learning)+(AI+OR+%22machine+learning%22+OR+%22neural+network%22)+when:7d&hl=en-US&gl=US&ceid=US:en",
    "arXiv AI": "https://rss.arxiv.org/rss/cs.AI",
    "arXiv Machine Learning": "https://rss.arxiv.org/rss/cs.LG",

    # Anthropic / Claude / Claude Code
    # anthropic.com/rss.xml returns 404 - proxy via Google News (same trick as the
    # Musk feed below). Two queries: company/model news, and Claude Code specifically.
    "Anthropic News (via Google News)": "https://news.google.com/rss/search?q=Anthropic+OR+%22Claude+Opus%22+OR+%22Claude+Sonnet%22+when:2d&hl=en-US&gl=US&ceid=US:en",
    "Claude Code (via Google News)": "https://news.google.com/rss/search?q=%22Claude+Code%22+OR+%22Claude+Agent+SDK%22+OR+%22Claude+Skills%22+when:3d&hl=en-US&gl=US&ceid=US:en",

    # xAI / Elon Musk AI
    "xAI Blog": "https://x.ai/blog/rss.xml",
    # Elon Musk posts on x.com — direct scraping requires auth (402), so we
    # proxy via Google News RSS filtered to site:x.com/elonmusk
    "Elon Musk on X (via Google News)": "https://news.google.com/rss/search?q=%22elon+musk%22+(xAI+OR+Grok+OR+AI)+site:x.com%2Felonmusk&hl=en-US&gl=US&ceid=US:en",

    # Open Models / Open Weights
    # Open-weight releases usually break on Hugging Face, Reddit and vendor blogs
    # a day or two before the general AI outlets pick them up, so this section gets
    # its own sources rather than living off the general feeds.
    # Probed 2026-09-07 — four candidates were rejected and are NOT worth retrying:
    #   mistral.ai/news/feed.xml, ai.meta.com/blog/rss/, lmstudio.ai/blog/rss.xml → 404
    #   qwenlm.github.io/blog/index.xml → 200 but abandoned (newest post 2025-09-22)
    #   papers.takara.ai/api/feed → 200 but lags ~4 days; arXiv AI/ML already covers papers
    "Open Models (via Google News)": "https://news.google.com/rss/search?q=(%22open+weights%22+OR+%22open-weight+model%22+OR+%22open+source+model%22)+(Llama+OR+Qwen+OR+DeepSeek+OR+Mistral+OR+Gemma+OR+Kimi+OR+GLM+OR+OLMo+OR+Falcon)+when:2d&hl=en-US&gl=US&ceid=US:en",
    "Open Model Benchmarks (via Google News)": "https://news.google.com/rss/search?q=(%22open+model%22+OR+%22open-weight%22+OR+%22open+source+LLM%22)+(benchmark+OR+leaderboard+OR+outperforms+OR+release)+when:3d&hl=en-US&gl=US&ceid=US:en",
    # Highest-yield open-model source by a wide margin (20 of 25 entries inside 24h
    # when probed). Community posts, so weight the *linked* release over the commentary.
    "r/LocalLLaMA": "https://www.reddit.com/r/LocalLLaMA/.rss",
    # Live but infrequent (roughly fortnightly) — carries local-model release notes.
    "Ollama Blog": "https://ollama.com/blog/rss.xml",

    # Hackathons, Contests & Opportunities  (30-day window - see OPPORTUNITY_SOURCES)
    # These are things a reader can ENTER or APPLY TO, not news about them, so the
    # feed has to reach back much further than a day: a hackathon closing in three
    # weeks was announced last month. Probed 2026-09-07 - four dedicated platforms
    # were rejected and are NOT worth retrying:
    #   devpost.com/hackathons.rss     → HTTP 406 on both a bot UA and a browser UA
    #   mlh.io/seasons/2026/events.rss → HTTP 200 but zero entries (no longer RSS)
    #   hackerearth.com/challenges/feed/, indiaai.gov.in/rss and /feed → 404
    #   opportunitydesk.org/feed/ → live, but general opportunities (water prizes,
    #     film fellowships); the AI hit rate was too low to justify the noise
    # Google News search queries cover the same ground and were the only sources
    # that actually returned entrants: 57 / 17 / 6 / 74 entries when probed.
    "AI Hackathons (via Google News)": "https://news.google.com/rss/search?q=%22AI+hackathon%22+OR+%22hackathon%22+(AI+OR+%22artificial+intelligence%22+OR+%22machine+learning%22)+when:30d&hl=en-US&gl=US&ceid=US:en",
    "AI Competitions (via Google News)": "https://news.google.com/rss/search?q=(%22AI+challenge%22+OR+%22AI+competition%22+OR+%22AI+contest%22)+(prize+OR+submissions+OR+registration+OR+deadline)+when:30d&hl=en-US&gl=US&ceid=US:en",
    "AI Programs (via Google News)": "https://news.google.com/rss/search?q=(%22AI+accelerator+program%22+OR+%22AI+incubator%22+OR+%22AI+fellowship%22+OR+%22AI+residency%22)+(applications+OR+cohort+OR+apply)+when:30d&hl=en-US&gl=US&ceid=US:en",
    "AI Applications Open (via Google News)": "https://news.google.com/rss/search?q=(%22applications+open%22+OR+%22apply+now%22+OR+%22call+for+applications%22)+(AI+OR+%22artificial+intelligence%22)+(program+OR+cohort+OR+accelerator+OR+grant+OR+hackathon)+when:30d&hl=en-US&gl=US&ceid=US:en",

    # AI Tools & Business
    "Product Hunt AI": "https://www.producthunt.com/feed?category=artificial-intelligence",
    "Futurism": "https://futurism.com/feed",
}


# arXiv feeds return hundreds of papers — limit to most relevant
ARXIV_MAX_PER_FEED = 15

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

QUANTUM_SOURCES = {
    "arXiv Quantum Physics",
    "Quantum + AI (via Google News)",
}

OPPORTUNITY_SOURCES = {
    "AI Hackathons (via Google News)",
    "AI Competitions (via Google News)",
    "AI Programs (via Google News)",
    "AI Applications Open (via Google News)",
}

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


def fetch_feed(name, url, cutoff_time, timeout=15):
    """Fetch and parse a single RSS feed. Returns list of articles."""
    is_arxiv = name.startswith("arXiv")
    articles = []
    undated = 0
    try:
        response = requests.get(url, timeout=timeout, headers={
            "User-Agent": "GlobalAINews/1.0 (RSS Reader)"
        })
        response.raise_for_status()
        feed = feedparser.parse(response.content)

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

            article = {
                "title": getattr(entry, "title", "No title"),
                "url": getattr(entry, "link", ""),
                "source": name,
                "published": published.isoformat(),
                "published_date": published.strftime("%Y-%m-%d"),
                "summary": plain_summary(getattr(entry, "summary", getattr(entry, "description", ""))),
                "category": _categorize_source(name),
            }
            # Opportunity feeds are noisy by design (broad queries, wide window),
            # so every entry carries the gate's verdict and the curation step can
            # filter on a field rather than re-deriving the rule.
            if name in OPPORTUNITY_SOURCES:
                article["is_opportunity"] = qualifies_as_opportunity(
                    article["title"], article["summary"]
                )
            articles.append(article)

            # Cap arXiv to avoid flooding with hundreds of papers
            if is_arxiv and len(articles) >= ARXIV_MAX_PER_FEED:
                break

    except requests.exceptions.Timeout:
        print(f"  [TIMEOUT] {name} ({url})")
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] {name}: {e}")
    except Exception as e:
        print(f"  [PARSE ERROR] {name}: {e}")

    if undated:
        print(f"  [DROPPED {undated} undated] {name}")

    return articles


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

    Prefers a real publisher feed over a Google News proxy, then the entry with
    the most summary text, since proxy entries carry only the headline.
    """
    def rank(a):
        is_proxy = "Google News" in a.get("source", "")
        return (is_proxy, -len(a.get("summary") or ""))
    return sorted(members, key=rank)[0]


def deduplicate_stories(articles):
    """Collapse same-story duplicates. Returns (kept, removed_count).

    arXiv is exempt. Syndication is a NEWS phenomenon - the same press release
    rewritten by many outlets - whereas arXiv papers are never syndicated and
    papers within one subfield share so much vocabulary that title similarity
    produces false merges ("Codes for Quantum Secret Sharing with a Helper" vs
    "Quantum Secret Sharing with a Helper and Programmable Access Structures"
    are two different papers, 0.8 token overlap).
    """
    clusters = []  # [(tokens, [articles])]
    passthrough = []
    for article in articles:
        if article.get("source", "").startswith("arXiv"):
            passthrough.append(article)
            continue
        tokens = title_tokens(article.get("title", ""))
        for cluster_tokens, members in clusters:
            if _same_story(tokens, cluster_tokens):
                members.append(article)
                break
        else:
            clusters.append((tokens, [article]))

    kept = []
    for _, members in clusters:
        best = _representative(members)
        others = [m for m in members if m is not best]
        if others:
            # Corroboration is a useful relevance signal, so keep the trail.
            best["also_reported_by"] = sorted({m["source"] for m in others})
            best["duplicate_count"] = len(members)
        kept.append(best)

    kept.extend(passthrough)
    return kept, len(articles) - len(kept)


def _categorize_source(source_name):
    """Map source to broad category for initial sorting."""
    categories = {
        "indian": ["Inc42", "YourStory", "Economic Times Tech"],
        "quantum": ["arXiv Quantum Physics"],
        "ai_research": ["arXiv AI", "arXiv Machine Learning"],
        "showcase": ["Product Hunt AI"],
        "opportunity": [
            "AI Hackathons (via Google News)",
            "AI Competitions (via Google News)",
            "AI Programs (via Google News)",
            "AI Applications Open (via Google News)",
        ],
        "company_blog": ["OpenAI Blog", "Google AI Blog", "Hugging Face Blog"],
        "anthropic_claude": ["Anthropic News (via Google News)", "Claude Code (via Google News)"],
        "elon_xai": ["xAI Blog", "Elon Musk on X (via Google News)"],
        "open_model": [
            "Open Models (via Google News)",
            "Open Model Benchmarks (via Google News)",
            "r/LocalLLaMA",
            "Ollama Blog",
        ],
    }
    for cat, sources in categories.items():
        if source_name in sources:
            return cat
    return "general"


def scrape_all_feeds():
    """Scrape all RSS feeds and save to JSON."""
    os.makedirs(TMP_DIR, exist_ok=True)

    now = datetime.now(timezone.utc)
    is_quantum_day = now.weekday() == QUANTUM_WEEKDAY
    all_articles = []

    print(f"Scraping RSS feeds at {now.strftime('%Y-%m-%d %H:%M UTC')} ({now.strftime('%A')})")
    print(f"  default window : last {DEFAULT_WINDOW_HOURS}h")
    print(f"  quantum window : last {QUANTUM_WINDOW_HOURS}h "
          f"({'INCLUDED - quantum day' if is_quantum_day else 'SKIPPED - not Thursday'})")

    for name, url in FEEDS.items():
        is_quantum = name in QUANTUM_SOURCES
        if is_quantum and not is_quantum_day:
            print(f"  [ skipped   ] {name} (quantum runs Thursdays)")
            continue

        cutoff_time = now - timedelta(hours=window_hours_for(name))
        articles = fetch_feed(name, url, cutoff_time)
        w = window_hours_for(name)
        tag = f"{w // 24}d" if w >= 48 else f"{w}h"
        if name in OPPORTUNITY_SOURCES:
            kept = sum(1 for a in articles if a.get("is_opportunity"))
            tag += f", {kept}/{len(articles)} pass gate"
        print(f"  [{len(articles):>3} articles] {name}  ({tag})")
        all_articles.extend(articles)
        time.sleep(0.5)  # polite delay

    # Deduplicate by URL
    seen_urls = set()
    unique_articles = []
    for article in all_articles:
        if article["url"] and article["url"] not in seen_urls:
            seen_urls.add(article["url"])
            unique_articles.append(article)

    # Collapse the same story reported by multiple outlets
    unique_articles, dup_removed = deduplicate_stories(unique_articles)
    print(f"\nSame-story dedupe: removed {dup_removed} duplicate reports")

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
            "sources_scraped": len(FEEDS),
            "articles": unique_articles,
        }, f, indent=2, ensure_ascii=False)

    print(f"\nDone! {len(unique_articles)} unique articles saved to {OUTPUT_FILE}")
    return unique_articles


if __name__ == "__main__":
    scrape_all_feeds()
