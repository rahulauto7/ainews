"""
Shared page fetching and text extraction for the curation step.

Before 2026-09-15 the agent verified stories with WebSearch/WebFetch and with
curl one-liners it rewrote from scratch every morning. Each of those calls is a
separate model turn, and every turn re-sends the whole conversation, so a run
with ~70 searches and ~40 fetches reached 170-226 turns and 300k+ tokens of
context. These helpers do the same work in one process, in parallel, and hand
the agent only a short excerpt.

Used by fetch_articles.py, find_opportunities.py and builder_helpers.py.
"""

import json
import math
import os
import re
import urllib.parse
from datetime import datetime

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(PROJECT_ROOT, ".tmp")
RSS_FILE = os.path.join(TMP_DIR, "rss_articles.json")
DECODED_CACHE = os.path.join(TMP_DIR, "decoded_urls.json")

# A browser UA reads several sites that refuse WebFetch or a bot UA (Devpost
# pages, anthropic.com, most Indian publishers). See the workflow's Lessons.
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}


def load_articles():
    with open(RSS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data, data["articles"]


def local_date(iso_timestamp):
    """YYYY-MM-DD in this machine's timezone (IST). scraped_at is UTC, and a run
    before 05:30 IST would otherwise be dated the previous day."""
    return datetime.fromisoformat(iso_timestamp).astimezone().strftime("%Y-%m-%d")


def fetch_html(url, timeout=25):
    """GET a page. Returns (html, final_url). Raises requests exceptions."""
    r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    r.encoding = r.encoding or r.apparent_encoding
    return r.text, r.url


# ── Google News proxy links ───────────────────────────────────────────────────
# Proxy links (news.google.com/rss/articles/CBMi...) do not redirect to the
# publisher any more; the target has to be requested from Google's batchexecute
# endpoint with a signature and timestamp scraped from the article page.

def is_google_news(url):
    return "news.google.com" in (url or "")


# A cloud machine's request is often answered with Google's cookie-consent page
# (consent.google.com) instead of the article page, which carries no signature;
# every Google News item failed this way on the first cloud run, 2026-10-02.
# These cookies record consent already given, the way a returning browser does.
CONSENT_COOKIES = {"CONSENT": "YES+cb", "SOCS": "CAI"}


def _signature_page(aid, timeout):
    """(signature, timestamp) from the article page, trying both page paths.

    Raises ValueError naming what came back instead, so a failed run says whether
    it met a consent wall, a block or a changed page.
    """
    seen = []
    for path in ("articles", "rss/articles"):
        r = requests.get(f"https://news.google.com/{path}/{aid}", headers=HEADERS,
                         cookies=CONSENT_COOKIES, timeout=timeout)
        sg = re.search(r'data-n-a-sg="([^"]+)"', r.text)
        ts = re.search(r'data-n-a-ts="([^"]+)"', r.text)
        if sg and ts:
            return sg.group(1), ts.group(1)
        seen.append(f"/{path}: HTTP {r.status_code} from {urllib.parse.urlparse(r.url).netloc}")
    raise ValueError("Google News page carried no decoding signature (" + "; ".join(seen) + ")")


def _decode_google_news_uncached(url, timeout=20):
    aid = urllib.parse.urlparse(url).path.rstrip("/").split("/")[-1]
    sg, ts = _signature_page(aid, timeout)
    inner = ["garturlreq",
             [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None,
               None, None, None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
             aid, int(ts), sg]
    payload = [[["Fbv4je", json.dumps(inner), None, "generic"]]]
    r = requests.post(
        "https://news.google.com/_/DotsSplashUi/data/batchexecute",
        data={"f.req": json.dumps(payload)},
        headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        cookies=CONSENT_COOKIES, timeout=timeout,
    )
    r.raise_for_status()
    arr = json.loads(r.text.split("\n\n")[1])
    return json.loads(arr[0][2])[1]


def load_decoded_cache():
    try:
        with open(DECODED_CACHE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_decoded_cache(cache):
    os.makedirs(TMP_DIR, exist_ok=True)
    with open(DECODED_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=1)


def decode_google_news(url, cache=None):
    """Publisher URL for a Google News proxy link; other URLs pass through.

    The cache is keyed by the proxy URL itself, not by an index into
    rss_articles.json, so it stays correct after a re-scrape.
    """
    if not is_google_news(url):
        return url
    own_cache = cache is None
    cache = load_decoded_cache() if own_cache else cache
    if url in cache:
        return cache[url]
    try:
        target = _decode_google_news_uncached(url)
    except Exception:
        target = _decode_google_news_uncached(url)  # one retry; Google drops the odd request
    cache[url] = target
    if own_cache:
        save_decoded_cache(cache)
    return target


# ── X posts ───────────────────────────────────────────────────────────────────
# X has no keyless feed, but one post can be read in full through the embed
# endpoint the publishers' widgets use. It needs a token derived from the post id;
# without it the endpoint answers 404. Found and tested 2026-10-02.

TWEET_API = "https://cdn.syndication.twimg.com/tweet-result"


def is_x_url(url):
    """True for a link on X itself. Matched on the host: a substring test sent
    vox.com, spacex.com and netflix.com articles to the post reader."""
    host = urllib.parse.urlparse(url or "").netloc.lower().split(":")[0]
    for prefix in ("www.", "mobile."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    return host in ("x.com", "twitter.com")


def tweet_id(url):
    """The post id in an x.com or twitter.com status URL, or None."""
    m = re.search(r"/status(?:es)?/(\d+)", url or "")
    return m.group(1) if m else None


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


def fetch_tweet(url, timeout=20):
    """The embed JSON for one post. Raises on a URL with no post id or a non-200."""
    tid = tweet_id(url)
    if not tid:
        raise ValueError(f"no post id in {url}")
    r = requests.get(TWEET_API, params={"id": tid, "token": _tweet_token(tid), "lang": "en"},
                     headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()


def tweet_record(js):
    """Title, text and the post's own timestamp, from the embed JSON.

    Raises ValueError when the answer holds no post: a deleted, withheld or
    protected post comes back 200 as a TweetTombstone, and an empty record would
    read as a successful fetch with no text and no date.
    """
    if js.get("__typename") == "TweetTombstone" or not js.get("text") or not js.get("created_at"):
        raise ValueError(f"no post in the embed answer ({js.get('__typename') or 'empty'})")
    created = js.get("created_at") or ""
    text = js.get("text") or ""
    quoted = (js.get("quoted_tweet") or {}).get("text")
    if quoted:
        text += f"\nQuoted post: {quoted}"
    if js.get("in_reply_to_screen_name"):
        text += f"\nIn reply to @{js['in_reply_to_screen_name']}"
    return {"title": f"@{(js.get('user') or {}).get('screen_name', '?')} on X", "text": text,
            "published": created[:10], "published_at": created}


# ── Text extraction ───────────────────────────────────────────────────────────

_DATE_META = [
    ("property", "article:published_time"),
    ("name", "article:published_time"),
    ("itemprop", "datePublished"),
    ("name", "date"),
    ("name", "publish-date"),
    ("name", "parsely-pub-date"),
    ("name", "sailthru.date"),
    ("property", "og:published_time"),
]


def _iso_date(value):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", value or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def extract_published(soup, raw_html=""):
    """Best-effort YYYY-MM-DD the page says it was published, or None."""
    for attr, key in _DATE_META:
        tag = soup.find("meta", attrs={attr: key})
        if tag and _iso_date(tag.get("content")):
            return _iso_date(tag.get("content"))
    m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', raw_html)
    if m and _iso_date(m.group(1)):
        return _iso_date(m.group(1))
    t = soup.find("time", attrs={"datetime": True})
    if t and _iso_date(t["datetime"]):
        return _iso_date(t["datetime"])
    return None


def _clean(text):
    return " ".join((text or "").split())


def _json_ld_article_body(raw_html):
    """`articleBody` from the page's JSON-LD, if the publisher provides one."""
    for block in re.findall(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', raw_html):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                body = node.get("articleBody")
                if isinstance(body, str) and len(body) > 500:
                    return _clean(BeautifulSoup(body, "lxml").get_text(" "))
                stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
    return ""


def _densest_paragraphs(soup):
    """Paragraphs from the container holding the most paragraph text.

    Taking every <p> on the page pulls in promo blocks: Inc42 repeats three
    course adverts before the story. The story's own paragraphs share one
    parent, so group by parent and keep the heaviest group - or by grandparent
    when a site wraps each paragraph in its own div.
    """
    paras = []
    for p in soup.find_all("p"):
        line = _clean(p.get_text(" "))
        if len(line) > 40:
            paras.append((p, line))
    if not paras:
        return []
    total = sum(len(line) for _, line in paras)
    for level in (1, 2):
        weight = {}
        for p, line in paras:
            node = p
            for _ in range(level):
                node = node.parent if node.parent is not None else node
            weight[id(node)] = weight.get(id(node), 0) + len(line)
        best_id, best = max(weight.items(), key=lambda kv: kv[1])
        if best >= 0.4 * total or level == 2:
            out = []
            for p, line in paras:
                node = p
                for _ in range(level):
                    node = node.parent if node.parent is not None else node
                if id(node) == best_id and line not in out:
                    out.append(line)
            return out
    return []


def extract_article(raw_html):
    """Title, published date, description and body text of an article page.

    Body text is the longer of the publisher's JSON-LD `articleBody` (Economic
    Times has no <p> tags at all) and the paragraphs of the densest <p>
    container; all visible text is the fallback for client-rendered pages.
    """
    soup = BeautifulSoup(raw_html, "lxml")
    published = extract_published(soup, raw_html)
    title = ""
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        title = _clean(og["content"])
    elif soup.title:
        title = _clean(soup.title.get_text())
    desc = ""
    for attr, key in (("property", "og:description"), ("name", "description")):
        tag = soup.find("meta", attrs={attr: key})
        if tag and tag.get("content"):
            desc = _clean(tag["content"])
            break

    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "form"]):
        tag.decompose()

    # Each strategy fails somewhere, and each failure is a SHORTER text: some
    # publishers truncate articleBody to a teaser, BBC splits its story across
    # sibling blocks (so the densest container holds half of it), and Inc42's
    # <article> element is a promo card. So take the longest.
    article_paras = []
    for art in soup.find_all("article"):
        lines = [_clean(p.get_text(" ")) for p in art.find_all("p")]
        lines = [l for l in lines if len(l) > 40]
        if sum(map(len, lines)) > sum(map(len, article_paras)):
            article_paras = lines
    text = max(_json_ld_article_body(raw_html),
               "\n".join(_densest_paragraphs(soup)),
               "\n".join(dict.fromkeys(article_paras)),
               key=len)
    if len(text) < 300:
        text = _clean(soup.get_text(" "))
    return {"title": title, "published": published, "description": desc, "text": text}


def visible_text(raw_html):
    """All visible text on a page, whitespace-collapsed. For grep-style checks."""
    soup = BeautifulSoup(raw_html, "lxml")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return _clean(soup.get_text(" "))


def grep_context(text, pattern, width=160, max_matches=5, max_len=450):
    """Snippets of `text` around matches of `pattern`, overlapping ones merged
    and each capped at `max_len` characters (a Devpost prize table otherwise
    merges into one 2,000-character snippet)."""
    spans = []
    for m in re.finditer(pattern, text, flags=re.I):
        start, end = max(0, m.start() - width), min(len(text), m.end() + width)
        if spans and start <= spans[-1][1]:
            spans[-1][1] = max(spans[-1][1], end)
        else:
            spans.append([start, end])
        if len(spans) > max_matches:
            break
    out = []
    for s, e in spans[:max_matches]:
        e = min(e, s + max_len)
        out.append(("..." if s else "") + text[s:e] + ("..." if e < len(text) else ""))
    return out
