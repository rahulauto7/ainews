"""
Every hackathon platform the pipeline reads, as one list of events.

rahul, 2026-10-03: "search every platform for AI related hackathon", but "if they
are asking for any API ... don't use that platform". So every reader here uses
only what the platform's own website loads for any visitor - a public JSON
listing or the data embedded in the page - and nothing that needs a key, a token
or a sign-up. Kaggle, Eventbrite, Luma and Meetup offer only keyed APIs and are
not read directly; Kaggle, AIcrowd, DrivenData, Zindi, CodaLab and Codabench
competitions arrive through mlcontests.com's listing instead.

Platforms (probed 2026-10-03, all keyless):
  Devpost      devpost.com/api/hackathons - the JSON its listing page loads
  lablab.ai    lablab.ai/ai-hackathons - events in the page's Next.js chunks
  mlcontests   mlcontests.com - the page's data-competitions attribute
  HackerEarth  hackerearth.com/chrome-extension/events/ - public JSON
  Devfolio     devfolio.co/hackathons - the page's __NEXT_DATA__
  Unstop       unstop.com/api/public/opportunity/search-result - public JSON
  MLH          mlh.io/seasons/<year>/events - the page's data-page JSON
  TAIKAI       taikai.network/hackathons - the page's Apollo state
  Hackster     hackster.io/contests - the contest cards in the page
Tried and left out: hackathon.com (start dates only, no deadlines), Cerebral
Valley and lu.ma (in-person San Francisco meetups; Luma's API needs a key).

Each reader returns a list of event dicts:
  platform       "Devpost", "lablab.ai", ...
  key            stable id across runs ("devpost:12345"), for the watcher's seen-list
  name, url
  deadline       datetime.date of the submission deadline (IST), or None if not listed
  deadline_kind  "submission" when the platform names the submission deadline,
                 "end" when it gives only the event's end - the latest a submission
                 can be due. Never the registration deadline.
  prize, where   short display text, "" when unknown
  ai             True when the event is about AI (see is_ai)
  restricted     why it cannot be entered by anyone ("invite-only"), or ""

Used by find_opportunities.py (candidates for the daily AI Hackathons section)
and hackathon_watch.py (the hourly new-hackathon email). Needs only requests
and the standard library beyond web_text, so the GitHub workflow installs two
packages.
"""

import html as html_lib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import web_text

# rahul, 2026-10-03: "7 days is for build time ... exclude within 7 days
# submissions deadline not registration deadline". A hackathon is listed only
# when its SUBMISSION deadline is at least this many days after today.
MIN_BUILD_DAYS = 7

# Deadlines are compared as dates in rahul's timezone: the edition is dated in
# IST, and a deadline of 23:59 IST is that day, not the next one in UTC.
IST = timezone(timedelta(hours=5, minutes=30))

DEVPOST_API = "https://devpost.com/api/hackathons"
DEVPOST_THEME = "Machine Learning/AI"
LABLAB_LISTING = "https://lablab.ai/ai-hackathons"
MLCONTESTS = "https://mlcontests.com/"
HACKEREARTH_EVENTS = "https://www.hackerearth.com/chrome-extension/events/"
DEVFOLIO_LISTING = "https://devfolio.co/hackathons"
UNSTOP_API = "https://unstop.com/api/public/opportunity/search-result"
MLH_EVENTS = "https://mlh.io/seasons/{season}/events"
TAIKAI_LISTING = "https://taikai.network/hackathons"
HACKSTER_CONTESTS = "https://www.hackster.io/contests"

JSON_HEADERS = {**web_text.HEADERS, "Accept": "application/json"}


# ── Dates and the build-time rule ────────────────────────────────────────────

def today_ist(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(IST).date()


def days_to_build(deadline, today):
    """Whole days from `today` to the submission deadline, or None if unknown."""
    return (deadline - today).days if deadline else None


def has_build_time(deadline, today):
    """True when the submission deadline leaves MIN_BUILD_DAYS or more to build."""
    days = days_to_build(deadline, today)
    return days is not None and days >= MIN_BUILD_DAYS


def ist_date(timestamp):
    """The IST date of an ISO timestamp ("2026-10-04T18:29:00Z", "... +05:30"),
    or None. A timestamp with no zone is taken as UTC."""
    if not timestamp:
        return None
    try:
        dt = datetime.fromisoformat(str(timestamp).strip().replace("Z", "+00:00").replace(" ", "T", 1))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST).date()


_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
# A month name or its abbreviation, and nothing longer: "23 marketing" is no date.
_MON = (r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
        r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b\.?")
_ISO_RE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_DAY_MON_RE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+" + _MON + r"(?:,?\s+(\d{4}))?\b", re.I)
_MON_DAY_RE = re.compile(r"\b" + _MON + r"\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s+(\d{4})\b)?", re.I)


def _date_mentions(text):
    """[(position, year or None, month, day)] for every date written in `text`."""
    out = []
    for m in _ISO_RE.finditer(text):
        out.append((m.start(), int(m.group(1)), int(m.group(2)), int(m.group(3))))
    for m in _DAY_MON_RE.finditer(text):
        out.append((m.start(), int(m.group(3)) if m.group(3) else None,
                    _MONTHS[m.group(2).lower()[:3]], int(m.group(1))))
    for m in _MON_DAY_RE.finditer(text):
        out.append((m.start(), int(m.group(3)) if m.group(3) else None,
                    _MONTHS[m.group(1).lower()[:3]], int(m.group(2))))
    return sorted(out)


def parse_deadline(text, today=None):
    """The submission deadline written in `text` as a date, or None.

    Reads "23 Oct 2026", "October 23, 2026", "2026-10-23", "23 Oct 2026, 11:45 PM
    PT" and ranges ("Sep 01 - Oct 23, 2026"), taking the LAST date written, which
    is where a range ends. A date with no year takes the year of a later date in
    the same text, else the one that puts it nearest after `today` (a date more
    than 60 days past is read as next year's).
    """
    if not text:
        return None
    if isinstance(text, (date, datetime)):
        return text if not isinstance(text, datetime) else text.date()
    mentions = _date_mentions(str(text))
    if not mentions:
        return None
    _, year, month, day = mentions[-1]
    if year is None:
        later_years = [y for _, y, _, _ in mentions if y]
        if later_years:
            year = later_years[-1]
        else:
            today = today or today_ist()
            year = today.year
            try:
                if date(year, month, day) < today - timedelta(days=60):
                    year += 1
            except ValueError:
                return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def devpost_deadline(period):
    """End of a Devpost submission_period_dates string.

    Devpost writes "Oct 02 - 04, 2026" (same month), "Sep 01 - Oct 23, 2026" and
    "Dec 15, 2025 - Jan 05, 2026"; the first form has no month after the dash.
    """
    m = re.search(r"-\s*(?:([A-Za-z]{3})[a-z]*\s+)?(\d{1,2}),\s*(\d{4})\s*$", period or "")
    if m and not m.group(1):
        first = re.match(r"\s*([A-Za-z]{3})", period)
        if first and first.group(1).lower() in _MONTHS:
            try:
                return date(int(m.group(3)), _MONTHS[first.group(1).lower()], int(m.group(2)))
            except ValueError:
                return None
    return parse_deadline(period)


# ── What counts as AI ────────────────────────────────────────────────────────

# "AI" and "ML" as their own token, so AI4Good and Hack4AI count but Dubai, mail
# and HTML do not.
AI_RE = re.compile(
    r"(?<![a-z])(ai|ml)(?![a-z])|\b(a\.i\.|artificial intelligence|machine learning|llms?|"
    r"genai|gen-ai|generative|agentic|ai agents?|gpt|chatgpt|deep learning|neural|"
    r"computer vision|nlp|data science|datathon|gemini|claude|openai|copilot|"
    r"diffusion|transformers?|reinforcement learning)\b",
    re.I)


def is_ai(*texts):
    return bool(AI_RE.search(" ".join(t for t in texts if t)))


# ── Prize size ───────────────────────────────────────────────────────────────

# rahul, 2026-10-03: "in PDF, give me hackathons with our top prizes first".
# Rough rates, used only to put one prize ahead of another; the PDF prints the
# organiser's own figure.
TO_USD = {"$": 1.0, "usd": 1.0, "usdc": 1.0, "usdt": 1.0, "dollars": 1.0,
          "€": 1.1, "eur": 1.1, "euros": 1.1, "£": 1.3, "gbp": 1.3, "pounds": 1.3,
          "₹": 1 / 85, "inr": 1 / 85, "rs": 1 / 85, "rupees": 1 / 85}
_SCALE = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mn": 1e6, "million": 1e6,
          "lakh": 1e5, "lakhs": 1e5, "crore": 1e7, "crores": 1e7, "cr": 1e7}
# An amount with its currency on either side: "$138k", "₹ 1,00,000", "€10,680",
# "Rs. 2 lakh", "20,000 EUR", "5,000 USDC", "10,000€". A number with no currency
# ("19 cash prizes", "1st") is not money.
_MONEY_RE = re.compile(
    r"(?:(?P<pre>[$€£₹])|\b(?P<code>usd|eur|gbp|inr|rs)(?![a-z])\.?)?\s?"
    r"(?<![\d.,])(?P<num>\d[\d,]*(?:\.\d+)?)"
    r"(?:\s?(?P<scale>million|thousand|lakhs?|crores?|mn|cr|k|m)\b)?"
    r"(?:\s?(?P<post>usdc|usdt|usd|eur|gbp|inr|dollars|euros|pounds|rupees)\b|(?P<postsym>[€£₹]))?",
    re.I)
# "$100k in AWS credits" is not cash, so it never outranks "$25k cash".
_CREDITS_RE = re.compile(r"\s*(?:in\s+)?(?:[\w.+-]+\s+){0,2}credits?\b", re.I)


def prize_usd(text):
    """Rough US-dollar size of a prize line: its largest cash amount, 0 when none.

    The largest, because a curated line reads "$138k cash total ($25k 1st)" and
    the total is never smaller than any one prize in it.
    """
    text, best = str(text or ""), 0.0
    for m in _MONEY_RE.finditer(text):
        currency = m.group("pre") or m.group("code") or m.group("post") or m.group("postsym")
        if not currency or _CREDITS_RE.match(text, m.end()):
            continue
        try:
            value = float(m.group("num").rstrip(",.").replace(",", ""))
        except ValueError:
            continue
        value *= _SCALE.get((m.group("scale") or "").lower(), 1)
        best = max(best, value * TO_USD[currency.lower()])
    return best


def by_prize(stories):
    """The AI Hackathons section in print order: biggest prize first. Stable, so
    equal prizes and stories with no prize (last) keep the curator's order."""
    return sorted(stories, key=lambda s: -prize_usd(s.get("prize")))


def event(platform, key, name, url, deadline, deadline_kind, prize="", where="", ai=True,
          restricted=""):
    return {"platform": platform, "key": key, "name": " ".join((name or "").split()) or key,
            "url": url, "deadline": deadline, "deadline_kind": deadline_kind,
            "prize": " ".join((prize or "").split()), "where": " ".join((where or "").split()),
            "ai": bool(ai), "restricted": restricted}


def _norm_url(url):
    p = urlparse(url if "//" in url else "https://" + url)
    return (p.netloc.replace("www.", "") + p.path).rstrip("/").lower()


def _still_open(events, today):
    """Drop events whose deadline has already passed (unknown deadlines stay)."""
    return [e for e in events if e["deadline"] is None or e["deadline"] >= today]


# ── Devpost ──────────────────────────────────────────────────────────────────

def devpost_rows(params, pages):
    """Devpost's own listing JSON (nine rows a page). Returns (rows, total)."""
    rows, total = [], None
    for page in range(1, pages + 1):
        r = requests.get(DEVPOST_API, headers=JSON_HEADERS, params={**params, "page": page}, timeout=25)
        r.raise_for_status()
        data = r.json()
        total = data.get("meta", {}).get("total_count")
        rows += data.get("hackathons", [])
        if not data.get("hackathons") or (total and len(rows) >= total):
            break
    return rows, total


def devpost_event(h):
    themes = {t.get("name") for t in h.get("themes") or []}
    prize = re.sub(r"<[^>]+>", "", h.get("prize_amount") or "")
    cash = (h.get("prizes_counts") or {}).get("cash", 0)
    return event("Devpost", f"devpost:{h.get('id') or _norm_url(h['url'])}", h.get("title"), h["url"],
                 devpost_deadline(h.get("submission_period_dates")), "submission",
                 prize=f"{prize} ({cash} cash prizes)" if cash else ("" if prize in ("", "$0") else prize),
                 where=(h.get("displayed_location") or {}).get("location", ""),
                 ai=DEVPOST_THEME in themes or is_ai(h.get("title")),
                 restricted="invite-only" if h.get("invite_only") else "")


def read_devpost(today, pages=3):
    """The newest open and upcoming events: the AI theme listing, plus the "AI"
    search for events filed under another theme. Newest first, so an hourly check
    sees a new event on the first page."""
    seen, out = set(), []
    for params in ({"themes[]": DEVPOST_THEME}, {"search": "AI"}):
        rows, _ = devpost_rows({"status[]": ["open", "upcoming"], "order_by": "recently-added", **params},
                               pages)
        for h in rows:
            e = devpost_event(h)
            if e["key"] not in seen:
                seen.add(e["key"])
                out.append(e)
    return _still_open(out, today)


# ── lablab.ai ────────────────────────────────────────────────────────────────

def parse_lablab_listing(html, now):
    """lablab.ai events that have not ended, soonest end first:
    [{slug, name, start, end, end_at, signup}].

    lablab.ai has no API and no feed; the events sit in the page's Next.js data
    chunks. Each record opens {"id":..,"name":..}, then carries signupActive and the
    endAt/startAt pair, then its slug and type. Workshops and other non-hackathon
    types are dropped.
    """
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, flags=re.S)
    if not chunks:
        return []
    data = json.loads('"' + "".join(chunks) + '"')
    seen = {}
    for m in re.finditer(r'"endAt":"([^"]+)","startAt":"([^"]+)"', data):
        after = data[m.end(): m.end() + 1500]
        before = data[max(0, m.start() - 6000): m.start()]
        slug = re.search(r'"slug":"([a-z0-9-]+)","previousSlugs"', after)
        kind = re.search(r'"type":"([A-Z_]+)"', after)
        signup = re.search(r'"signupActive":(true|false)', before[-300:])
        names = list(re.finditer(r'\{"id":"[^"]+","name":"((?:[^"\\]|\\.)*)"', before))
        if not slug or not kind or kind.group(1) != "HACKATHON":
            continue
        end = datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
        if end > now:
            # The nearest record opening before this endAt, unless another
            # record's endAt sits in between (a description too long to span).
            own = names and '"endAt"' not in before[names[-1].end():]
            name = json.loads(f'"{names[-1].group(1)}"') if own else slug.group(1)
            seen.setdefault(slug.group(1), {"slug": slug.group(1), "name": name,
                                            "start": m.group(2)[:10], "end": m.group(1)[:10],
                                            "end_at": m.group(1),
                                            "signup": bool(signup and signup.group(1) == "true")})
    return sorted(seen.values(), key=lambda e: e["end"])


def lablab_events(listing):
    return [event("lablab.ai", f"lablab:{e['slug']}", e["name"],
                  f"https://lablab.ai/ai-hackathons/{e['slug']}", ist_date(e["end_at"]), "end",
                  where="Online", ai=True, restricted="" if e["signup"] else "sign-up closed")
            for e in listing]


def read_lablab(today):
    html, _ = web_text.fetch_html(LABLAB_LISTING)
    return _still_open(lablab_events(parse_lablab_listing(html, datetime.now(timezone.utc))), today)


# ── mlcontests.com (Kaggle, AIcrowd, DrivenData, Zindi, CodaLab, ...) ────────

def parse_mlcontests(html, today):
    m = re.search(r'data-competitions="([^"]*)"', html)
    if not m:
        return []
    out = []
    for c in json.loads(html_lib.unescape(m.group(1))):
        url = re.sub(r"[?&]ref=mlcontests$", "", c.get("url") or "")
        if not url:
            continue
        # "deadline" is the final submission deadline; "registration-deadline",
        # when given, is earlier and does not count.
        out.append(event("mlcontests", f"mlcontests:{_norm_url(url)}", c.get("name"), url,
                         parse_deadline(c.get("deadline"), today), "submission",
                         prize=c.get("prize") or "",
                         where="" if c.get("platform") in (None, "Independent") else c["platform"], ai=True))
    return _still_open(out, today)


def read_mlcontests(today):
    html, _ = web_text.fetch_html(MLCONTESTS)
    return parse_mlcontests(html, today)


# ── HackerEarth ──────────────────────────────────────────────────────────────

def parse_hackerearth(data, today):
    out = []
    for e in (data or {}).get("response") or []:
        url = e.get("url") or ""
        # The feed mixes hackathons with hiring challenges (/challenges/competitive/).
        if "/challenges/hackathon/" not in url:
            continue
        out.append(event("HackerEarth", f"hackerearth:{_norm_url(url)}", e.get("title"), url,
                         ist_date(e.get("end_utc_tz") or e.get("end_tz")), "end", where="Online",
                         ai=is_ai(e.get("title"), e.get("description"))))
    return _still_open(out, today)


def read_hackerearth(today):
    r = requests.get(HACKEREARTH_EVENTS, headers=JSON_HEADERS, timeout=25)
    r.raise_for_status()
    return parse_hackerearth(r.json(), today)


# ── Devfolio ─────────────────────────────────────────────────────────────────

def _next_data(html):
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, flags=re.S)
    return json.loads(m.group(1)) if m else {}


def parse_devfolio(html, today):
    """Open and upcoming hackathons from the listing page's own data. ends_at is
    the hackathon's end; settings.reg_ends_at is only the registration deadline."""
    out, seen = [], set()
    for query in (_next_data(html).get("props", {}).get("pageProps", {})
                  .get("dehydratedState", {}).get("queries", [])):
        data = (query.get("state") or {}).get("data")
        if not isinstance(data, dict):
            continue
        for group in ("open_hackathons", "upcoming_hackathons", "featured_hackathons"):
            for h in data.get(group) or []:
                slug = h.get("slug")
                if not slug or slug in seen:
                    continue
                seen.add(slug)
                themes = " ".join(((t.get("theme") or {}).get("name") or "") for t in h.get("themes") or [])
                out.append(event("Devfolio", f"devfolio:{slug}", h.get("name"), f"https://{slug}.devfolio.co/",
                                 ist_date(h.get("ends_at")), "end",
                                 where="Online" if h.get("is_online") else "In person",
                                 ai=is_ai(h.get("name"), themes)))
    return _still_open(out, today)


def read_devfolio(today):
    html, _ = web_text.fetch_html(DEVFOLIO_LISTING)
    return parse_devfolio(html, today)


# ── Unstop ───────────────────────────────────────────────────────────────────

def parse_unstop(data, today):
    """Unstop search results. end_date is the competition's end; the registration
    deadline (regnRequirements.end_regn_dt) is deliberately not read."""
    rows = (data or {}).get("data") or []
    if isinstance(rows, dict):
        rows = rows.get("data") or []
    out = []
    for rec in rows:
        url = rec.get("seo_url") or ""
        if not url.startswith("http"):
            url = f"https://unstop.com/{(rec.get('public_url') or '').lstrip('/')}"
        skills = " ".join(s.get("skill_name") or s.get("skill") or "" for s in rec.get("required_skills") or [])
        org = (rec.get("organisation") or {}).get("name", "")
        prizes = [p for p in rec.get("prizes") or [] if isinstance(p, dict)]
        cash = sum(p.get("cash") or 0 for p in prizes if isinstance(p.get("cash"), (int, float)))
        symbol = {"fa-rupee": "₹", "fa-dollar": "$", "fa-euro": "€"}.get(
            (prizes[0].get("currency") if prizes else "") or "", "")
        prize = f"{symbol}{cash:,} total cash" if cash else ""
        out.append(event("Unstop", f"unstop:{rec.get('id') or _norm_url(url)}", rec.get("title"), url,
                         ist_date(rec.get("end_date")), "end", prize=prize,
                         where=" | ".join(x for x in (rec.get("region") or "", org) if x),
                         ai=is_ai(rec.get("title"), skills)))
    return _still_open(out, today)


def read_unstop(today):
    r = requests.get(UNSTOP_API, params={"opportunity": "hackathons", "per_page": 30, "oppstatus": "open",
                                         "searchTerm": "AI"}, headers=JSON_HEADERS, timeout=25)
    r.raise_for_status()
    return parse_unstop(r.json(), today)


# ── Major League Hacking ─────────────────────────────────────────────────────

def parse_mlh(html, today):
    m = re.search(r'<script data-page="app" type="application/json">(.*?)</script>', html, flags=re.S)
    if not m:
        return []
    props = json.loads(m.group(1)).get("props") or {}
    out = []
    for e in props.get("upcomingEvents") or []:
        if e.get("status") == "ended":
            continue
        focus = " ".join((e.get("customFields") or {}).get("hackathon_focus") or [])
        where = e.get("location") or ""
        if e.get("formatType") == "digital":
            where = "Online"
        url = e.get("websiteUrl") or f"https://mlh.io{e.get('url') or ''}"
        out.append(event("MLH", f"mlh:{e.get('slug') or _norm_url(url)}", e.get("name"), url,
                         ist_date(e.get("endsAt")), "end", where=where, ai=is_ai(e.get("name"), focus)))
    return _still_open(out, today)


def read_mlh(today):
    # MLH seasons run August to July and are named for the year they end in.
    season = today.year + 1 if today.month >= 8 else today.year
    html, _ = web_text.fetch_html(MLH_EVENTS.format(season=season))
    return parse_mlh(html, today)


# ── TAIKAI ───────────────────────────────────────────────────────────────────

def parse_taikai(html, today):
    """Open challenges from the page's Apollo cache. The listing carries each
    step's start but no end, so the last step's start stands in for the end."""
    state = _next_data(html).get("props", {}).get("apolloState") or {}

    def ref(r):
        return state.get(r["__ref"], {}) if isinstance(r, dict) and "__ref" in r else (r or {})

    out = []
    for key, c in state.items():
        if not key.startswith("Challenge:") or c.get("isClosed"):
            continue
        org = ref(c.get("organization"))
        starts = [ref(s).get("startDate") for s in c.get("steps") or []]
        ends = [d for d in (ist_date(s) for s in starts if s) if d]
        industries = " ".join(ref(i).get("title") or "" for i in c.get("industries") or [])
        prize = ""
        if c.get("prize"):
            prize = f"{c['prize']:,} {ref(c.get('prizeCurrency')).get('name', '')}".strip()
        out.append(event("TAIKAI", f"taikai:{org.get('slug')}/{c.get('slug')}", c.get("name"),
                         f"https://taikai.network/{org.get('slug')}/hackathons/{c.get('slug')}",
                         max(ends) if ends else None, "end", prize=prize,
                         ai=is_ai(c.get("name"), c.get("shortDescription"), industries)))
    return _still_open(out, today)


def read_taikai(today):
    html, _ = web_text.fetch_html(TAIKAI_LISTING)
    return parse_taikai(html, today)


# ── Hackster.io ──────────────────────────────────────────────────────────────

# The stretch between a card's title and its date may not reach another
# contest's link, so a card in judging (no date) never borrows the next one's.
_HACKSTER_CARD = re.compile(
    r'href="/contests/([a-z0-9-]+)"><h4[^>]*>([^<]+)</h4></a>(?:(?!/contests/).){0,1500}?'
    r'Participation open until:</p><p[^>]*>([^<]+)</p>', re.S)


def parse_hackster(html, today):
    """Contests still taking entries: each card names the date participation
    closes. Cards in judging carry no such line and are skipped."""
    out, seen = [], set()
    for m in _HACKSTER_CARD.finditer(html):
        slug, title = m.group(1), html_lib.unescape(m.group(2))
        if slug in seen:  # each card is printed twice, for mobile and desktop
            continue
        seen.add(slug)
        out.append(event("Hackster", f"hackster:{slug}", title, f"https://www.hackster.io/contests/{slug}",
                         parse_deadline(m.group(3), today), "submission", where="Online", ai=is_ai(title)))
    return _still_open(out, today)


def read_hackster(today):
    html, _ = web_text.fetch_html(HACKSTER_CONTESTS)
    return parse_hackster(html, today)


# ── All of them ──────────────────────────────────────────────────────────────

PLATFORMS = (
    ("Devpost", read_devpost),
    ("lablab.ai", read_lablab),
    ("mlcontests", read_mlcontests),
    ("HackerEarth", read_hackerearth),
    ("Devfolio", read_devfolio),
    ("Unstop", read_unstop),
    ("MLH", read_mlh),
    ("TAIKAI", read_taikai),
    ("Hackster", read_hackster),
)


def collect(today=None, platforms=PLATFORMS):
    """Read every platform in parallel.

    Returns (events, errors): every event from the platforms that answered, and
    {platform: "ErrorType: message"} for the ones that did not. One platform
    failing never hides the others.
    """
    today = today or today_ist()

    def run(item):
        name, read = item
        try:
            return name, read(today), None
        except Exception as exc:  # noqa: BLE001 - reported per platform
            return name, [], f"{type(exc).__name__}: {str(exc)[:200]}"

    events, errors = [], {}
    with ThreadPoolExecutor(max_workers=len(platforms)) as ex:
        for name, got, err in ex.map(run, platforms):
            if err:
                errors[name] = err
            events += got
    return events, errors
