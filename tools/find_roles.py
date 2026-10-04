"""Open Forward Deployed and Solutions Engineer roles, for the careers section.

rahul, 2026-10-03: focus the PDF on "getting [a] remote AI job as forward
deployed eng or solution engineer in global companies, not [an] Indian company,
which work via remote and via visa". This finds those roles every morning, from
sources that need no key or sign-up:

  company job boards   the public posting APIs of Greenhouse, Ashby and Lever,
                       for the global AI companies in COMPANY_BOARDS
  Hacker News          the month's "Ask HN: Who is hiring?" thread, whose posts
                       say REMOTE and VISA outright (read through HN Algolia)
  Himalayas            remote-only roles with the countries each is open to; an
                       empty list means worldwide (Remotive was tried and dropped:
                       its free feed ignores the search and returns 16 stale jobs)

A role is kept when its title is in the FDE / Solutions family (TITLE_RE), it is
not a management or intern role, it was posted in the last ROLE_WINDOW_DAYS days,
and it is not an on-site or hybrid role in India (rahul wants global companies,
remote or by visa). Kept roles are ranked for rahul: remote and open to India
first, then roles whose posting says the company sponsors visas, then remote
roles limited to another region, then on-site roles abroad that say nothing
about visas. Newest first within each tier.

Usage:
  python3 tools/find_roles.py            # fetch, write .tmp/roles.json, print the top
  python3 tools/find_roles.py --top 20

The builder takes the table from .tmp/roles.json with builder_helpers.open_roles().
"""

import argparse
import concurrent.futures as cf
import html
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import web_text

ROLES_FILE = os.path.join(web_text.TMP_DIR, "roles.json")
ROLE_WINDOW_DAYS = 30
TIMEOUT = 25

# Global AI companies that hire Forward Deployed and Solutions Engineers and post
# on a keyless board. Probed 2026-10-03: each answered with jobs and at least one
# title in the family. (name, board, slug).
COMPANY_BOARDS = [
    ("Anthropic", "greenhouse", "anthropic"),
    ("OpenAI", "ashby", "openai"),
    ("Cohere", "ashby", "cohere"),
    ("Scale AI", "greenhouse", "scaleai"),
    ("Databricks", "greenhouse", "databricks"),
    ("Palantir", "lever", "palantir"),
    ("ElevenLabs", "ashby", "elevenlabs"),
    ("Glean", "greenhouse", "gleanwork"),
    ("Sierra", "ashby", "sierra"),
    ("Decagon", "ashby", "decagon"),
    ("Harvey", "ashby", "harvey"),
    ("Writer", "ashby", "writer"),
    ("Cresta", "greenhouse", "cresta"),
    ("Cursor", "ashby", "cursor"),
    ("Cognition", "ashby", "cognition"),
    ("LangChain", "ashby", "langchain"),
    ("Modal", "ashby", "modal"),
    ("Baseten", "ashby", "baseten"),
    ("Together AI", "greenhouse", "togetherai"),
    ("Deepgram", "ashby", "deepgram"),
    ("Synthesia", "ashby", "synthesia"),
    ("Snorkel AI", "greenhouse", "snorkelai"),
    ("Labelbox", "greenhouse", "labelbox"),
    ("Perplexity", "ashby", "perplexity"),
    ("Replit", "ashby", "replit"),
    ("n8n", "ashby", "n8n"),
    ("Supabase", "ashby", "supabase"),
    ("Vercel", "greenhouse", "vercel"),
    ("Intercom", "greenhouse", "intercom"),
    ("CoreWeave", "greenhouse", "coreweave"),
    ("Nebius", "greenhouse", "nebius"),
    ("Snowflake", "ashby", "snowflake"),
]

TITLE_RE = re.compile(
    r"forward[- ]deployed|solutions? (?:engineer|architect|consultant)|"
    r"applied ai engineer|deployment (?:engineer|strategist)|"
    r"customer engineer|(?:pre-?)?sales engineer|ai engineer, (?:enterprise|customer)",
    re.I,
)
SENIORITY_SKIP = re.compile(
    r"\b(?:manager|director|head|vp|vice president|chief|intern|internship|"
    r"program lead|apprentice)\b", re.I)
INDIA_RE = re.compile(
    r"\b(?:india|bengaluru|bangalore|mumbai|delhi|new delhi|gurgaon|gurugram|"
    r"hyderabad|pune|chennai|noida|kolkata|ahmedabad)\b", re.I)
# A city in the title ("Forward Deployed Engineer - Bangalore, India") ties a role
# to an Indian office even when a remote board lists it.
INDIA_CITY_RE = re.compile(INDIA_RE.pattern.replace("india|", ""), re.I)
# Roles from the open boards (Himalayas, Hacker News) must be AI work; the company
# boards are all AI companies. A Forward Deployed title counts on its own.
AI_RE = re.compile(r"\b(?:ai|a\.i\.|llms?|genai|generative|machine learning|ml|agents?|"
                   r"agentic|forward[- ]deployed)\b", re.I)
# A region in the title overrides an empty "worldwide" restriction list.
TITLE_REGION_RE = re.compile(r"\b(?:EU|EMEA|US|USA|UK|LATAM|Americas|North America|Europe|"
                             r"Canada|Brazil|Germany|France|Spain|Mexico)\b")
# A remote role rahul can take from India: open worldwide, or to Asia, or India.
OPEN_REGION_RE = re.compile(
    r"\b(?:worldwide|anywhere|global|international|apac|asia|asia[- ]pacific|"
    r"india)\b", re.I)

# Visa wording in a posting. A refusal wins over loose positive phrasing ("we do
# not offer visa support"), but not over an outright "we do sponsor visas".
VISA_STRONG = re.compile(
    r"\bwe (?:do |can |will )?sponsor (?:work )?visas?\b|\bvisa sponsorship (?:is )?"
    r"(?:available|offered|provided)\b|\bwe do sponsor\b", re.I)
VISA_POSITIVE = re.compile(
    r"\bvisa sponsorship\b|\bsponsor(?:ship)? (?:of |for )?(?:work )?visas?\b|"
    r"\bvisa (?:support|assistance)\b|\brelocation (?:and|&) visa\b", re.I)
VISA_NEGATIVE = re.compile(
    r"\b(?:not|unable to|cannot|can't|don't|do not|won't|will not|no)\s+"
    r"(?:be able to\s+|currently\s+)?(?:offer\s+|provide\s+)?(?:visa\s+)?sponsor|"
    r"\bno visa\b|\bsponsorship is not available\b|\bwithout (?:visa )?sponsorship\b",
    re.I)


VISA_SCOPE = re.compile(r"\bsponsor (?:work )?visas? (?:to|for|in) (?:the )?([A-Z][A-Za-z]+(?: [A-Z][a-z]+)?)")


def visa_scope(text):
    """The one country a posting limits its sponsorship to ("We can sponsor visas
    to Germany"), or None."""
    m = VISA_SCOPE.search(text or "")
    return m.group(1) if m else None


def visa_status(text):
    """True when the posting says the company sponsors visas, False when it says
    it does not, None when it says nothing."""
    text = text or ""
    if VISA_STRONG.search(text):
        return True
    if VISA_NEGATIVE.search(text):
        return False
    if VISA_POSITIVE.search(text):
        return True
    return None


def plain(text):
    """HTML (possibly entity-escaped twice, as Greenhouse sends it) to plain text."""
    text = html.unescape(html.unescape(text or ""))
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


def _day(value):
    """YYYY-MM-DD from an ISO string or epoch milliseconds, or None."""
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date().isoformat()
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return str(value)[:10] or None


def _mode(location, workplace=None, remote_flag=None):
    """remote / hybrid / onsite / unknown, from the board's fields and the location text."""
    workplace = (workplace or "").lower().replace("-", "").replace(" ", "")
    if workplace in ("remote",):
        return "remote"
    if workplace in ("hybrid",):
        return "hybrid"
    if workplace in ("onsite", "inoffice", "office"):
        return "onsite"
    if re.search(r"\bremote\b", location or "", re.I):
        return "remote"
    if remote_flag is True and not workplace:
        return "remote"
    return "unknown" if not location else "onsite"


def role(company, title, location, mode, visa, posted, url, source):
    return {"company": company, "title": " ".join((title or "").split()),
            "location": " ".join((location or "").split()), "mode": mode, "visa": visa,
            "posted": posted, "url": url, "source": source}


# ── Readers: each returns [role] for one source ───────────────────────────────

def read_greenhouse(company, slug, get=requests.get):
    base = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    jobs = get(base, headers=web_text.HEADERS, timeout=TIMEOUT).json().get("jobs", [])
    out = []
    for j in jobs:
        if not TITLE_RE.search(j.get("title", "")):
            continue
        location = (j.get("location") or {}).get("name", "")
        out.append(role(company, j.get("title"), location, _mode(location), None,
                        _day(j.get("first_published") or j.get("updated_at")),
                        j.get("absolute_url"), f"greenhouse:{slug}") | {"_id": j.get("id")})
    return out


def greenhouse_visa(slug, job_id, get=requests.get):
    """(visa, scope) from one Greenhouse posting's text (the list omits it)."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}"
    text = plain(get(url, headers=web_text.HEADERS, timeout=TIMEOUT).json().get("content", ""))
    return visa_status(text), visa_scope(text)


def read_ashby(company, slug, get=requests.get):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    jobs = get(url, headers=web_text.HEADERS, timeout=TIMEOUT).json().get("jobs", [])
    out = []
    for j in jobs:
        if not TITLE_RE.search(j.get("title", "")) or j.get("isListed") is False:
            continue
        location = j.get("location") or ""
        text = j.get("descriptionPlain") or plain(j.get("descriptionHtml"))
        out.append(role(company, j.get("title"), location,
                        _mode(location, j.get("workplaceType"), j.get("isRemote")),
                        visa_status(text), _day(j.get("publishedAt")),
                        j.get("jobUrl") or j.get("applyUrl"), f"ashby:{slug}")
                   | {"visa_scope": visa_scope(text)})
    return out


def read_lever(company, slug, get=requests.get):
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    jobs = get(url, headers=web_text.HEADERS, timeout=TIMEOUT).json()
    out = []
    for j in jobs if isinstance(jobs, list) else []:
        if not TITLE_RE.search(j.get("text", "")):
            continue
        location = (j.get("categories") or {}).get("location", "")
        text = " ".join(str(j.get(k) or "") for k in ("descriptionPlain", "additionalPlain"))
        out.append(role(company, j.get("text"), location, _mode(location, j.get("workplaceType")),
                        visa_status(text), _day(j.get("createdAt")), j.get("hostedUrl"),
                        f"lever:{slug}") | {"visa_scope": visa_scope(text)})
    return out


HN_SEARCH = "https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&hitsPerPage=5"
HN_ITEM = "https://hn.algolia.com/api/v1/items/{}"


def parse_hn_post(post):
    """A role from one top-level "Who is hiring?" comment, or None.

    The convention is a first line of pipe-separated fields - company, role(s),
    place, REMOTE / ONSITE, VISA - before the description.
    """
    raw = post.get("text") or ""
    first = plain(re.split(r"<p>|\n", raw, maxsplit=1)[0])
    body = plain(raw)
    match = TITLE_RE.search(first) or TITLE_RE.search(body)
    if not match or "|" not in first or not AI_RE.search(body):
        return None
    fields = [f.strip() for f in first.split("|") if f.strip()]
    company = fields[0][:60]
    title_field = next((f for f in fields[1:] if TITLE_RE.search(f)), None)
    title = title_field or match.group(0).title()
    head = first.lower()
    remote = bool(re.search(r"\bremote\b", head)) and not re.search(r"\b(?:no|not) remote\b", head)
    if re.search(r"\bno visa\b|\bvisa: ?no\b", head):
        visa = False
    elif re.search(r"\bvisa\b", head):
        visa = True
    else:
        visa = visa_status(body)
    if not remote and visa is not True:
        return None
    place = [f for f in fields[1:] if f is not title_field and not re.match(r"https?://", f)
             and not re.fullmatch(r"(?i)(?:full[- ]time|part[- ]time|contract|visa)", f)]
    return role(company, title, ", ".join(place)[:80], "remote" if remote else "onsite", visa,
                _day(post.get("created_at")),
                f"https://news.ycombinator.com/item?id={post.get('id')}", "hn")


def read_hn(get=requests.get):
    hits = get(HN_SEARCH, headers=web_text.HEADERS, timeout=TIMEOUT).json().get("hits", [])
    thread = next((h for h in hits if h.get("title", "").startswith("Ask HN: Who is hiring")), None)
    if not thread:
        return []
    item = get(HN_ITEM.format(thread["objectID"]), headers=web_text.HEADERS, timeout=TIMEOUT).json()
    return [r for r in (parse_hn_post(c) for c in item.get("children") or []) if r]


HIMALAYAS = "https://himalayas.app/jobs/api/search?q={}"
# (query, worldwide only). The plain FDE search keeps every region, because a
# remote FDE role is rare enough to be worth seeing even when limited to a region.
HIMALAYAS_QUERIES = (("forward deployed engineer", False), ("forward deployed", True),
                     ("solutions engineer", True), ("solutions architect", True))


def read_himalayas(get=requests.get):
    out, seen = [], set()
    for query, worldwide in HIMALAYAS_QUERIES:
        url = HIMALAYAS.format(requests.utils.quote(query)) + ("&worldwide=true" if worldwide else "")
        for j in get(url, headers=web_text.HEADERS, timeout=TIMEOUT).json().get("jobs", []):
            key = j.get("guid") or j.get("applicationLink")
            if key in seen or not TITLE_RE.search(j.get("title", "")):
                continue
            seen.add(key)
            if not AI_RE.search(f"{j.get('title', '')} {j.get('companyName', '')}"):
                continue
            countries = j.get("locationRestrictions") or []
            place = ", ".join(countries[:3]) + (" and more" if len(countries) > 3 else "")
            text = plain(j.get("description") or j.get("excerpt"))
            out.append(role(j.get("companyName"), j.get("title"),
                            f"Remote ({place or 'worldwide'})", "remote", visa_status(text),
                            _day((j.get("pubDate") or 0) * 1000), j.get("applicationLink"),
                            "himalayas") | {"visa_scope": visa_scope(text)})
    return out


# ── Filter and rank ───────────────────────────────────────────────────────────

def keep(r, today):
    """Why a role is dropped, or None to keep it."""
    if not TITLE_RE.search(r["title"]):
        return "not an FDE or Solutions title"
    if SENIORITY_SKIP.search(r["title"]):
        return "management or intern role"
    if not r.get("url"):
        return "no link"
    if r.get("posted"):
        try:
            age = (date.fromisoformat(today) - date.fromisoformat(r["posted"])).days
        except ValueError:
            age = 0
        if age > ROLE_WINDOW_DAYS:
            return f"posted {age} days ago"
    if r["mode"] != "remote" and INDIA_RE.search(r["location"]):
        return "on-site or hybrid in India"
    if INDIA_CITY_RE.search(r["title"]) and not re.search(r"(?i)\bremote\b", r["title"]):
        return "tied to an office in India"
    return None


def open_to_india(r):
    """A remote role rahul can take from India."""
    if r["mode"] != "remote" or TITLE_REGION_RE.search(r["title"]):
        return False
    rest = re.sub(r"(?i)\bremote\b", "", r["location"]).strip(" ,-()/")
    return not rest or bool(OPEN_REGION_RE.search(rest))


def sponsors_here(r):
    """The posting says the company sponsors visas, and not only for another country."""
    scope = r.get("visa_scope")
    return r.get("visa") is True and (not scope or scope.lower() in r["location"].lower())


def tier(r):
    """0 remote and open to India, 1 sponsors visas, 2 remote elsewhere, 3 visa not stated."""
    if open_to_india(r):
        return 0
    if sponsors_here(r):
        return 1
    if r["mode"] == "remote":
        return 2
    return 3


def rank(roles, today):
    """Kept roles, best for rahul first: by tier, then newest."""
    kept = [r for r in roles if keep(r, today) is None]
    unique = {}
    for r in kept:
        unique.setdefault((r["company"].lower(), r["title"].lower(), r["location"].lower()), r)
    return sorted(unique.values(), key=lambda r: (tier(r), -_ordinal(r.get("posted"))))


def _ordinal(day):
    try:
        return date.fromisoformat(day).toordinal()
    except (TypeError, ValueError):
        return 0


def where(r):
    """The place column: where the job is and how it is worked."""
    location = r["location"] or "Location not stated"
    if r["mode"] == "remote":
        return location if re.search(r"(?i)\bremote\b", location) else f"Remote ({location})"
    if r["mode"] == "hybrid":
        return f"{location}, hybrid"
    return location


def visa_note(r):
    """The visa column. A scope elsewhere still prints ("Germany only"), so the
    reader sees why a sponsoring role abroad ranks lower."""
    if r.get("visa") is True:
        return f"sponsors visas ({r['visa_scope']} only)" if r.get("visa_scope") else "sponsors visas"
    if r.get("visa") is False:
        return "no visa sponsorship"
    return "" if r["mode"] == "remote" else "visa not stated"


SOURCE_NAMES = {"hn": "Hacker News \"Who is hiring?\"", "himalayas": "Himalayas"}


# Both of rahul's routes get seats in the table, whatever the day's mix: remote roles
# open to India, and roles abroad whose posting says the company sponsors visas.
TIER_SEATS = {0: 5, 1: 4}


def pick(ranked, limit=10, per_company=2):
    """The roles the table shows: TIER_SEATS first, then the best of the rest, at
    most `per_company` per company, in rank order."""
    chosen, count = [], {}

    def take(r):
        key = r["company"].lower()
        if r in chosen or count.get(key, 0) >= per_company or len(chosen) >= limit:
            return
        count[key] = count.get(key, 0) + 1
        chosen.append(r)

    for t, seats in TIER_SEATS.items():
        for r in [r for r in ranked if tier(r) == t]:
            if sum(1 for c in chosen if tier(c) == t) >= seats:
                break
            take(r)
    for r in ranked:
        take(r)
    order = {id(r): i for i, r in enumerate(ranked)}
    return sorted(chosen, key=lambda r: order[id(r)])


def table_rows(ranked, limit=10, per_company=2):
    """Rows for the PDF's standing-table layout.

    use_case is the company, model the role (linked to the posting), maker where
    it is and access the visa position; why says when and where it was posted.
    """
    rows = []
    for r in pick(ranked, limit, per_company):
        source = r["source"].split(":")[0]
        on = SOURCE_NAMES.get(source, f"{r['company']}'s careers page")
        try:
            day = date.fromisoformat(r.get("posted") or "")
            posted = f"{day.day} {day:%b}"
        except ValueError:
            posted = "date not given"
        rows.append({"use_case": r["company"], "model": r["title"], "maker": where(r),
                     "access": visa_note(r), "why": f"Posted {posted} on {on}.",
                     "url": r["url"]})
    return rows


# ── Run ───────────────────────────────────────────────────────────────────────

GREENHOUSE_VISA_CHECKS = 4  # newest postings per Greenhouse company read in full


def collect(today, get=requests.get):
    """(roles, failures) from every source, in parallel."""
    jobs = {f"{name} ({board})": (lambda n=name, b=board, s=slug:
                                  {"greenhouse": read_greenhouse, "ashby": read_ashby,
                                   "lever": read_lever}[b](n, s, get=get))
            for name, board, slug in COMPANY_BOARDS}
    jobs["Hacker News"] = lambda: read_hn(get=get)
    jobs["Himalayas"] = lambda: read_himalayas(get=get)
    roles, failures = [], []
    with cf.ThreadPoolExecutor(12) as ex:
        futures = {ex.submit(fn): label for label, fn in jobs.items()}
        for fut in cf.as_completed(futures):
            try:
                roles += fut.result()
            except Exception as exc:  # noqa: BLE001 - one board down must not stop the rest
                failures.append(f"{futures[fut]}: {type(exc).__name__}: {str(exc)[:80]}")
    # Greenhouse lists carry no description, so read the newest few that would
    # otherwise show as "visa not stated".
    pending = {}
    for r in roles:
        if r["source"].startswith("greenhouse:") and keep(r, today) is None and r["mode"] != "remote":
            pending.setdefault(r["source"], []).append(r)
    checks = [r for rs in pending.values()
              for r in sorted(rs, key=lambda r: -_ordinal(r.get("posted")))[:GREENHOUSE_VISA_CHECKS]]
    with cf.ThreadPoolExecutor(12) as ex:
        futures = {ex.submit(greenhouse_visa, r["source"].split(":", 1)[1], r["_id"], get): r
                   for r in checks}
        for fut in cf.as_completed(futures):
            try:
                futures[fut]["visa"], futures[fut]["visa_scope"] = fut.result()
            except Exception:  # noqa: BLE001 - the role stays, as "visa not stated"
                pass
    for r in roles:
        r.pop("_id", None)
    return roles, failures


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()

    today = datetime.now().strftime("%Y-%m-%d")
    roles, failures = collect(today)
    ranked = rank(roles, today)
    os.makedirs(web_text.TMP_DIR, exist_ok=True)
    with open(ROLES_FILE, "w", encoding="utf-8") as f:
        json.dump({"as_of": today, "roles": ranked}, f, indent=1, ensure_ascii=False)

    tiers = [sum(1 for r in ranked if tier(r) == t) for t in range(4)]
    print(f"{len(roles)} FDE/Solutions roles read, {len(ranked)} kept: {tiers[0]} remote and open to "
          f"India, {tiers[1]} sponsor visas, {tiers[2]} remote elsewhere, {tiers[3]} visa not stated")
    for line in failures:
        print(f"!! {line}")
    for r in ranked[:args.top]:
        print(f"  [{tier(r)}] {r['posted'] or '?':10s} {r['company'][:16]:16s} {r['title'][:46]:46s} "
              f"{where(r)[:30]:30s} {visa_note(r)}")
    print(f"Wrote {ROLES_FILE}; the builder takes the table with open_roles()")
    return 0


if __name__ == "__main__":
    sys.exit(main())
