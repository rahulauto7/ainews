"""
Read a hackathon's own page and decide whether rahul can enter it and win cash.

rahul, 2026-10-12: "Only give me cash-based price hackathons, like hackathons
with more than $5,000 in prizes. And online hackathons and check eligibility as
well before sending mail, like Indian working professional in IOCL ... make sure
that when you send it, I can sign up, and that the registration date is not in
the past."

So before an alert goes out, hackathon_watch.py hands each candidate that
passed the listing's own facts (AI, online or not stated, registration not
closed, 7+ days to build) to check(), which reads the event's page (Devpost: the
page and its /rules; Zindi and Kaggle: their public JSON, which carries the
rules) and looks
for:

  cash       the prize money, in rough US dollars (hackathon_sources.prize_usd).
             Devpost's listing figure counts swag and credits, so its page's
             "$45,000 in cash" wins. At least MIN_CASH_USD.
  online     an in-person or hybrid event is out; when the listing does not say,
             the page has to say online, virtual or remote.
  sign-up    "registration closed", or a registration period that has ended.
  who        rahul is an Indian citizen living in India and a working
             professional at IOCL, a state-owned company. Out: students-only
             events, events limited to residents of countries that do not
             include India, events that exclude India, events that exclude
             government or state-owned company employees, and events only for
             one company's staff or members.

Checks are deliberately strict: an event whose page says "open to students and
professionals" passes, one that says only "students" does not. A page that
cannot be read is not passed; the watcher tries again next run.
"""

import json
import re
from datetime import date

import requests

import hackathon_sources as hs
import web_text

MIN_CASH_USD = 5000

# Words that let a "students" or "residents" sentence through.
_OPEN_TO_ALL = re.compile(
    r"\b(worldwide|world-wide|global(ly)?|all countries|any country|every country|international(ly)?|"
    r"anyone|everyone|open to all|professionals?|developers?|working|non-students?|individuals over)\b", re.I)
_NEGATION = re.compile(r"\b(not open|is not open|are not eligible|not eligible|ineligible|excluded|excluding|"
                       r"except|exception|may not (?:enter|participate)|cannot (?:enter|participate)|"
                       r"prohibited|void|not (?:a )?(?:legal )?(?:residents?|citizens?|nationals?) of)\b", re.I)
_INDIA = re.compile(r"\bindia(n)?\b", re.I)

_STUDENTS_ONLY = re.compile(
    r"\b(?:(?:only|exclusively)\b[^.;]{0,50}\bstudents?\b|students?\s+only\b|"
    r"open\s+(?:only\s+)?to\s+(?:current(?:ly)?\s+|enrolled\s+|full[- ]time\s+)?"
    r"(?:university\s+|college\s+|high\s+school\s+|undergraduate\s+|graduate\s+)?students?\b|"
    r"must\s+be\s+(?:a\s+|an\s+)?(?:current(?:ly)?\s+)?(?:enrolled|full[- ]time\s+student|student)\b)",
    re.I)
_RESIDENTS_ONLY = re.compile(
    r"\b(?:(?:open|available|limited|restricted|eligible)\b[^.;]{0,60}\b(?:legal\s+)?"
    r"(?:residents?|citizens?|nationals?)\s+of\b|must\s+be\s+(?:a\s+)?(?:legal\s+)?(?:resident|citizen)s?\s+of\b|"
    r"specific countries/territories included\b|"
    r"(?:only|exclusively)\b[^.;]{0,40}\b(?:live|living|reside|residing|based|located)\s+in\b)", re.I)
# Devpost's "Who can participate" box: its own tags, read as tags.
_DEVPOST_STUDENTS = re.compile(r"\b(?:high school |college |university )?students only\b", re.I)
_GOVERNMENT = re.compile(r"\b(government(?:al)?|state[- ]owned|public[- ]sector|public official|"
                         r"government[- ](?:owned|controlled))\b", re.I)
_STAFF_ONLY = re.compile(r"\b(?:only|exclusively)\s+(?:open\s+)?(?:to|for)\s+(?:the\s+)?"
                         r"(?:employees|staff|members|customers)\s+of\b", re.I)
_IN_PERSON = re.compile(r"\b(in[- ]person|on[- ]site|onsite|offline|venue|hybrid|presencial)\b", re.I)
_ONLINE = re.compile(r"\b(online|virtual|remote(ly)?|remoto)\b", re.I)
_REG_CLOSED = re.compile(r"\b(registrations?\s+(?:is\s+|are\s+|has\s+|have\s+)?(?:now\s+)?closed|"
                         r"registration\s+(?:has\s+)?ended|no longer accepting (?:registrations|participants))\b",
                         re.I)
# "Registration Period: September 29, 2026 (10:00 am UTC) - October 27, 2026 (1:00 pm UTC)":
# the last date before the next heading is when registration closes.
_REG_PERIOD = re.compile(r"registration period:?\s*(.{0,140}?)(?:[\"“(]\s*registration period|"
                         r"submission period|judging period|$)", re.I | re.S)
_CASH_LINE = re.compile(r"[^.;\n]{0,80}\b(prizes?|cash|award|reward|pool|win|winners?|bounty)\b[^.;\n]{0,80}", re.I)
_DEVPOST_CASH = re.compile(r"[$€£₹]\s?[\d,]+(?:\s?[A-Z]{3})?\s+in\s+cash", re.I)


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.;!?])\s+|\s+[•·]\s+|\n+", text) if s.strip()]


def page_text(e, timeout=25):
    """The text a decision is made from: the event page, plus Devpost's rules
    page and Zindi's rules JSON. Raises on a page that cannot be read."""
    if e["platform"] == "Zindi":
        cid = e["key"].split(":", 1)[1]
        r = requests.get(f"{hs.ZINDI_API}/{cid}", headers=hs.JSON_HEADERS, timeout=timeout)
        r.raise_for_status()
        data = r.json().get("data") or {}
        texts = [m for m in re.findall(r'"text":\s*"((?:[^"\\]|\\.)*)"', json.dumps(data))]
        return "\n".join([data.get("subtitle") or ""] + [json.loads(f'"{t}"') for t in texts])
    kaggle = re.match(r"https://www\.kaggle\.com/(?:c|competitions)/([\w-]+)", e["url"])
    if kaggle:
        return kaggle_text(kaggle.group(1), timeout)
    html, _ = web_text.fetch_html(e["url"], timeout=timeout)
    text = web_text.visible_text(html)
    if e["platform"] == "Devpost":
        # Devpost's menu ("Host an internal hackathon") comes before the event's own text.
        start = text.find("Join hackathon")
        text = text[start:] if start >= 0 else text
        rules, _ = web_text.fetch_html(e["url"].rstrip("/") + "/rules", timeout=timeout)
        text += "\n" + web_text.visible_text(rules)
    return text


def kaggle_text(slug, timeout=25):
    """A Kaggle competition's overview, prizes and rules. Its pages are drawn in
    the browser, but the JSON calls they make need only the session cookie the
    page sets, no API key."""
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0"  # a full browser string gets an HTML page back, not JSON
    s.get(f"https://www.kaggle.com/competitions/{slug}", timeout=timeout).raise_for_status()
    headers = {"x-xsrf-token": s.cookies.get("XSRF-TOKEN") or "", "content-type": "application/json"}
    api = "https://www.kaggle.com/api/i/competitions."
    r = s.post(api + "CompetitionService/GetCompetition", json={"competitionName": slug},
               headers=headers, timeout=timeout)
    r.raise_for_status()
    comp = r.json()
    r = s.post(api + "PageService/ListPages", json={"competitionId": comp["id"]}, headers=headers, timeout=timeout)
    r.raise_for_status()
    reward = comp.get("reward") or {}
    head = [comp.get("title") or "", comp.get("briefDescription") or "", "Online competition on Kaggle."]
    if reward.get("quantity") and reward.get("id") in ("USD", "EUR", "GBP"):
        head.append(f"Total prizes: {reward['quantity']:,} {reward['id']}. {reward.get('clarification') or ''}")
    if comp.get("prohibitNewEntrantsExplicitDeadline"):
        head.append(f"Entry deadline: {comp['prohibitNewEntrantsExplicitDeadline'][:10]}.")
    pages = [re.sub(r"<[^>]+>", " ", p.get("content") or "") for p in r.json().get("pages") or []]
    return "\n".join(head + pages)


def cash_usd(e, text):
    """Rough US-dollar cash prize: Devpost's own "in cash" figure, else the
    listing's prize, else the largest amount the page names next to a prize word."""
    if e["platform"] == "Devpost":
        amounts = [hs.prize_usd(m.group(0)) for m in _DEVPOST_CASH.finditer(text)]
        if amounts:
            return max(amounts)
        return 0.0  # a Devpost prize with no cash is swag, credits or gift cards
    listed = hs.prize_usd(e["prize"])
    if listed:
        return listed
    return max((hs.prize_usd(m.group(0)) for m in _CASH_LINE.finditer(text)), default=0.0)


def who_problems(text):
    """Why rahul (Indian citizen in India, working at state-owned IOCL) could not
    enter or win, from the page text. Empty when nothing rules rahul out."""
    problems = []
    # Devpost's "Who can participate" box has no full stops and is read as tags;
    # it outranks the description ("open to all" next to a "Students only" tag).
    box = re.search(r"Who can participate (Above|Ages|All countries|Specific|Professionals|Students|High school|"
                    r"College|University|Companies)(.{0,700}?)(?:No countries/territories match|View schedule|$)",
                    text, re.S)
    if box:
        tags = box.group(1) + box.group(2)
        if _DEVPOST_STUDENTS.search(tags):
            problems.append(("students only", "Devpost: " + _DEVPOST_STUDENTS.search(tags).group(0)))
        if "countries/territories included" in tags.lower() and not _INDIA.search(tags):
            problems.append(("only some countries, not India", "Devpost: " + tags[:200]))
        if "countries/territories excluded" in tags.lower() and _INDIA.search(tags):
            problems.append(("India excluded", "Devpost: " + tags[:200]))
    for s in _sentences(text):
        # "Rising Star Award (Student Only)" limits one prize, not who can enter.
        if _STUDENTS_ONLY.search(s) and not _OPEN_TO_ALL.search(s) and not _NEGATION.search(s) \
                and not re.search(r"\b(award|prize|track|category|bonus)\b", s, re.I):
            problems.append(("students only", s))
        if _RESIDENTS_ONLY.search(s) and not _NEGATION.search(s):
            if "countries/territories included" in s.lower() and not _INDIA.search(s):
                problems.append(("only some countries, not India", s))
            elif not _INDIA.search(s) and not _OPEN_TO_ALL.search(s) \
                    and "countries/territories included" not in s.lower():
                problems.append(("only residents of other countries", s))
        if _NEGATION.search(s) and _INDIA.search(s) and "indiana" not in s.lower():
            problems.append(("India excluded", s))
        if _NEGATION.search(s) and _GOVERNMENT.search(s) and re.search(
                r"\b(employees?|officials?|staff|personnel|officers?)\b", s, re.I):
            problems.append(("government or state-owned company staff excluded (IOCL is state-owned)", s))
        if _STAFF_ONLY.search(s):
            problems.append(("only for one organisation's staff or members", s))
    seen, out = set(), []
    for reason, s in problems:
        if reason not in seen:
            seen.add(reason)
            out.append((reason, " ".join(s.split())[:220]))
    return out


def registration_closes(text, today):
    """The end of a stated registration period, or None."""
    m = _REG_PERIOD.search(text)
    if m:
        return hs.parse_deadline(m.group(1), today)
    m = re.search(r"Entry deadline: (\d{4}-\d{2}-\d{2})\.", text)
    return date.fromisoformat(m.group(1)) if m else None


def who_can_enter(text):
    """One short line for the email saying who can enter, when the page says."""
    if re.search(r"open to residents of the United States and worldwide, except", text):
        return "Anyone worldwide, except residents of sanctioned regions (Kaggle's standard rules)"
    box = re.search(r"Who can participate(.{0,300}?)(?:Specific countries|View full rules|×|$)", text, re.S)
    if box:
        return " ".join(box.group(1).split())[:160]
    m = (re.search(r"[^.;\n]{0,40}\b(open (?:only )?to|who can (?:join|participate|compete))\b[^.;\n]{0,140}",
                   text, re.I)
         or re.search(r"[^.;\n]{0,40}\beligib\w*\b[^.;\n]{0,140}", text, re.I))
    return " ".join(m.group(0).split())[:180] if m else ""


def check(e, text, today=None):
    """{"ok", "reasons", "cash_usd", "reg_closes", "who"} for one event."""
    today = today or hs.today_ist()
    reasons = []
    cash = cash_usd(e, text)
    if cash < MIN_CASH_USD:
        reasons.append(f"cash prize under ${MIN_CASH_USD:,}" + (f" (about ${cash:,.0f})" if cash else " (none found)"))
    if e.get("online") is False:
        reasons.append("in person or hybrid")
    elif e.get("online") is None:
        head = text[:3000]
        if _IN_PERSON.search(head) and not _ONLINE.search(head):
            reasons.append("in person (the page names a venue and no online option)")
        elif not _ONLINE.search(text):
            reasons.append("not stated to be online")
    reg = e.get("reg_closes") or registration_closes(text, today)
    if reg and reg < today:
        reasons.append(f"registration closed {reg:%d %b}")
    elif _REG_CLOSED.search(text):
        reasons.append("registration closed")
    for reason, evidence in who_problems(text):
        reasons.append(f"{reason}: \"{evidence}\"")
    return {"ok": not reasons, "reasons": reasons, "cash_usd": cash,
            "reg_closes": reg if reg and reg >= today else None, "who": who_can_enter(text)}


def as_dict(result):
    out = dict(result)
    if isinstance(out.get("reg_closes"), date):
        out["reg_closes"] = out["reg_closes"].isoformat()
    return out
