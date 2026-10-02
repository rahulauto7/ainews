"""
Back-fill and verify the two opportunity sections without web searches.

On 2026-09-14 and 2026-09-15 about 30 of the runs' ~70 web searches were
opportunity back-fill ("AI hackathon cash prize deadline October 2026 devpost")
and deadline checks, each one a model turn that re-sent the whole context.

Usage:
  python3 tools/find_opportunities.py devpost
      Open and upcoming Devpost hackathons tagged Machine Learning/AI, largest
      prize first, with cash-prize counts. Marks entries printed in the last
      three editions or rejected before.

  python3 tools/find_opportunities.py check URL [URL ...]
      Fetch each organiser page in parallel (plus /rules for Devpost) and print
      only the lines that decide publication: closed/ended status, deadline,
      prize and eligibility snippets.

  python3 tools/find_opportunities.py recheck
      `check` every opportunity printed in the last three editions - the
      carry-forward candidates - in one call.

  python3 tools/find_opportunities.py platforms
      New hackathons from four platforms, one block each: lablab.ai (open
      events, soonest end first, each event page checked), Devpost's newest
      "AI" events that the theme listing above does not show, Devfolio and
      Unstop. One platform failing prints "!! <platform>: <error>" and the
      others still print. prep_run.py writes this to .tmp/hackathons.txt.
"""

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import web_text
from builder_helpers import OPPORTUNITY_KEYS, prior_editions
from fetch_articles import fetch_one

DEVPOST_API = "https://devpost.com/api/hackathons"
LABLAB_LISTING = "https://lablab.ai/ai-hackathons"
DEVFOLIO_API = "https://api.devfolio.co/api/search/hackathons"
UNSTOP_API = "https://unstop.com/api/public/opportunity/search-result"
DEVPOST_THEME = "Machine Learning/AI"

ENDED = (r"this hackathon has ended|submissions? (are |is )?(now )?closed|"
         r"applications? (are |is |have )?(now )?closed|no longer accept|"
         r"registrations? (is |are )?closed|winners (have been )?announced|has been removed")
DEADLINE = (r"deadline|apply by|applications? (close|due|open until)|closes on|closing date|"
            r"last date|due date|submit by|register by|registration closes|submission period")
PRIZE = (r"(\$|US\$|USD|€|£|₹|INR|Rs\.?) ?\d[\d,.]*( ?(k|m|million|lakh|crore))?\b[^.]{0,30}"
         r"(cash|prize|stipend|grant|award|funding)|in cash|cash prize|prize pool|stipend")
ELIGIBLE = (r"eligib|students? only|currently enrolled|undergraduate|ph\.?d|citizens? of|"
            r"residents? of|excluded countries|excluding|age of majority|years of age|"
            r"open to (all|anyone|individuals|teams|professionals)")


def _norm_url(url):
    p = urlparse(url if "//" in url else "https://" + url)
    return (p.netloc.replace("www.", "") + p.path).rstrip("/").lower()


def history():
    """({normalised url: [dates printed]}, {normalised name: (date, reason)})."""
    printed, rejected = {}, {}
    for date, edition in prior_editions():
        for key in OPPORTUNITY_KEYS:
            for s in edition.get("sections", {}).get(key, []):
                for u in {s.get("url"), s.get("apply_url")} - {None, ""}:
                    printed.setdefault(_norm_url(u), []).append(date[5:])
        for r in (edition.get("curation_log") or {}).get("rejected", []):
            rejected.setdefault(r["name"].lower(), (r["date"], r["reason"]))
    return printed, rejected


# Rough conversion, used only to sort and filter; the printed figure is Devpost's own.
_TO_USD = {"$": 1.0, "€": 1.1, "£": 1.3, "₹": 1 / 85}
MIN_USD = 1000


def _usd(prize_text):
    m = re.match(r"\s*([$€£₹])\s*([\d,]+)", prize_text)
    return float(m.group(2).replace(",", "")) * _TO_USD[m.group(1)] if m else 0.0


def _marks(url, name, printed, rejected):
    """'printed mm-dd' / 'rejected mm-dd: reason' flags for one opportunity."""
    flags = []
    seen = printed.get(_norm_url(url)) if url else None
    if seen:
        flags.append("printed " + ",".join(sorted(set(seen))))
    rej = rejected.get((name or "").lower())
    if rej:
        flags.append(f"rejected {rej[0][5:]}: {rej[1][:60]}")
    return flags


def _devpost_fields(h):
    h["_prize"] = re.sub(r"<[^>]+>", "", h.get("prize_amount") or "") or "-"
    h["_cash"] = (h.get("prizes_counts") or {}).get("cash", 0)
    return h


def _devpost_line(h, printed, rejected):
    prize, cash = h["_prize"], h["_cash"]
    flags = []
    if not cash:
        flags.append("NO CASH PRIZES")
    if h.get("invite_only"):
        flags.append("INVITE-ONLY " + (h.get("eligibility_requirement_invite_only_description") or "")[:60])
    flags += _marks(h["url"], h["title"], printed, rejected)
    where = (h.get("displayed_location") or {}).get("location", "")
    return (f"- {prize:>10} ({cash} cash) | {h['title'][:70]} | {h.get('submission_period_dates')} "
            f"({h.get('time_left_to_submission')}) | {where[:20]} | {h['url']}"
            + (" | " + " | ".join(flags) if flags else ""))


def _devpost_rows(params, pages):
    rows, total = [], None
    for page in range(1, pages + 1):
        r = requests.get(DEVPOST_API, headers={**web_text.HEADERS, "Accept": "application/json"},
                         params={**params, "page": page}, timeout=25)
        r.raise_for_status()
        data = r.json()
        total = data.get("meta", {}).get("total_count")
        rows += data.get("hackathons", [])
        if not data.get("hackathons") or (total and len(rows) >= total):
            break
    return [_devpost_fields(h) for h in rows], total


def devpost(pages, show_all=False):
    printed, rejected = history()
    rows, total = _devpost_rows({"status[]": ["open", "upcoming"], "themes[]": DEVPOST_THEME,
                                 "order_by": "prize-amount"}, pages)
    shown = [h for h in rows if show_all or (h["_cash"] and _usd(h["_prize"]) >= MIN_USD)]
    shown.sort(key=lambda h: -_usd(h["_prize"]))

    print(f"Devpost: {len(rows)} of {total} open/upcoming Machine Learning/AI hackathons; "
          f"{len(rows) - len(shown)} hidden (no cash prize or under ~${MIN_USD:,}; --all shows them)")
    print("Prize figures include non-cash value; confirm cash on the /rules page before publishing.")
    for h in shown:
        print(_devpost_line(h, printed, rejected))


def _report(url, rec, rules=None):
    lines = [f"== {url}"]
    if rec.get("error"):
        lines.append(f"  {rec['error']}")
        return "\n".join(lines)
    page = rec.get("page") or rec.get("text") or ""
    if len(page) < 400:
        lines.append(f"  THIN    : only {len(page)} chars of text - page renders client-side; "
                     "confirm from the organiser's press release or registration page")
    ended = web_text.grep_context(page, ENDED, width=80, max_matches=2)
    lines.append("  STATUS  : " + ("CLOSED? " + " / ".join(ended) if ended else "no closed/ended notice found"))
    for label, pattern in (("DEADLINE", DEADLINE), ("PRIZE", PRIZE), ("ELIGIBLE", ELIGIBLE)):
        for snip in web_text.grep_context(page, pattern, width=110, max_matches=3):
            lines.append(f"  {label:8}: {snip}")
    if rules is not None:
        if rules.get("error"):
            lines.append(f"  RULES   : {rules['error']}")
        else:
            rpage = rules.get("page") or ""
            for snip in web_text.grep_context(rpage, r"excluded|not eligible|residents of|cash", width=110, max_matches=4):
                lines.append(f"  RULES   : {snip}")
    return "\n".join(lines)


def _fetch_pages(urls):
    """{url: fetch_one record} for each URL, plus its /rules page on Devpost."""
    decoded = web_text.load_decoded_cache()
    jobs = []
    for url in urls:
        jobs.append(url)
        if urlparse(url).netloc.endswith(".devpost.com"):
            jobs.append(url.rstrip("/") + "/rules")
    with ThreadPoolExecutor(max_workers=6) as ex:
        return dict(zip(jobs, ex.map(lambda u: fetch_one(u, decoded), jobs)))


def check(urls):
    recs = _fetch_pages(urls)
    for url in urls:
        rules_url = url.rstrip("/") + "/rules"
        print(_report(url, recs[url], recs.get(rules_url) if rules_url in recs else None))


def recheck():
    urls, seen = [], set()
    for date, edition in prior_editions():
        for key in OPPORTUNITY_KEYS:
            for s in edition.get("sections", {}).get(key, []):
                u = s.get("url")
                if u and _norm_url(u) not in seen:
                    seen.add(_norm_url(u))
                    urls.append(u)
                    print(f"[{date[5:]}] {'hackathon' if key == 'ai_hackathons' else 'programme'}: "
                          f"{s['title'][:80]} | deadline printed: {s.get('deadline', '-')}")
    print()
    check(urls)


# ── New hackathons from other platforms (`platforms`) ────────────────────────

def parse_lablab_listing(html, now):
    """lablab.ai events that have not ended, soonest end first: [{slug, start, end, signup}].

    lablab.ai has no API and no feed; the events sit in the page's Next.js data
    chunks. Each record's endAt/startAt pair is followed by its slug and type, and
    preceded by signupActive. Workshops and other non-hackathon types are dropped.
    """
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


def lablab(printed, rejected):
    """Open lablab.ai hackathons, each followed by what its own page says about
    prize, eligibility and deadline. Prize lines often mix cash and credits
    ("$5k cash + $5k credits"), so the event page decides."""
    html, _ = web_text.fetch_html(LABLAB_LISTING)
    events = parse_lablab_listing(html, datetime.now(timezone.utc))
    print(f"lablab.ai: {len(events)} open hackathons, soonest end first")
    urls = [f"https://lablab.ai/ai-hackathons/{e['slug']}" for e in events]
    recs = _fetch_pages(urls)
    for event, url in zip(events, urls):
        rec = recs[url]
        name = re.split(r"\s+[|-]\s+lablab", rec.get("title") or "", flags=re.I)[0] or event["slug"]
        flags = ([] if event["signup"] else ["SIGNUP CLOSED"]) + _marks(url, name, printed, rejected)
        print(f"- {name[:70]} | {event['start']} to {event['end']} | {url}"
              + (" | " + " | ".join(flags) if flags else ""))
        print("\n".join(_report(url, rec).splitlines()[1:]))


def devpost_newest(printed, rejected, pages=3):
    """Devpost's newest open "AI" events in any theme: the ones the theme listing misses."""
    rows, total = _devpost_rows({"status[]": ["open", "upcoming"], "search": "AI",
                                 "order_by": "recently-added"}, pages)
    new = [h for h in rows
           if DEVPOST_THEME not in {t.get("name") for t in h.get("themes") or []}]
    print(f"Devpost newest: {len(rows)} of {total} open/upcoming matching 'AI', newest first; "
          f"{len(new)} are outside the {DEVPOST_THEME} theme listing")
    for h in new:
        print(_devpost_line(h, printed, rejected))


def _pick(rec, *keys):
    """First non-empty value among `keys`, as short text."""
    for key in keys:
        value = rec.get(key)
        if isinstance(value, dict):
            value = value.get("name") or value.get("title") or ""
        if isinstance(value, list):
            value = ", ".join(str(v.get("name", v) if isinstance(v, dict) else v) for v in value[:3])
        if value not in (None, "", [], {}):
            return " ".join(str(value).split())
    return ""


def format_devfolio(rec):
    """One Devfolio hackathon as a line. Field names beyond the ten seen on
    2 Oct 2026 are guesses: the keys line printed above the block shows the truth."""
    slug = rec.get("slug") or ""
    url = _pick(rec, "url", "hackathon_url") or (f"https://{slug}.devfolio.co/" if slug else "")
    dates = f"{_pick(rec, 'starts_at')[:10] or '?'} to {_pick(rec, 'ends_at')[:10] or '?'}"
    where = _pick(rec, "city", "country") or _pick(rec, "apply_mode")
    prize = _pick(rec, "prize_amount", "total_prize", "prizes", "prize") or "-"
    return name_line(_pick(rec, "name", "title") or slug or "?", dates, prize, where, url)


def format_unstop(rec):
    """One Unstop hackathon as a line. Field names beyond the ten seen on
    2 Oct 2026 are guesses: the keys line printed above the block shows the truth."""
    public = _pick(rec, "public_url", "seo_url")
    url = public if public.startswith("http") else (f"https://unstop.com/{public.lstrip('/')}" if public else "")
    regn = rec.get("regnRequirements") or {}
    end = _pick(rec, "end_date") or _pick(regn, "end_regn_dt")
    dates = f"{_pick(rec, 'start_date')[:10] or '?'} to {end[:10] or '?'}"
    prize = _pick(rec, "prizes", "prize", "total_prize") or "-"
    where = _pick(rec, "region") + (" | " + _pick(rec, "organisation") if _pick(rec, "organisation") else "")
    return name_line(_pick(rec, "title", "name") or "?", dates, prize, where, url)


def name_line(name, dates, prize, where, url):
    return f"- {prize[:40]:>10} | {name[:70]} | {dates} | {where[:30]} | {url}"


def devfolio(printed, rejected):
    r = requests.post(DEVFOLIO_API, json={"type": "application_open", "from": 0, "size": 10},
                      headers={**web_text.HEADERS, "Accept": "application/json"}, timeout=25)
    r.raise_for_status()
    hits = r.json().get("hits") or []
    if isinstance(hits, dict):
        hits = hits.get("hits") or []
    recs = [h.get("_source", h) for h in hits]
    print(f"Devfolio: {len(recs)} hackathons with applications open")
    if recs:
        print("  keys: " + ", ".join(sorted(recs[0])))
    for rec in recs:
        line = format_devfolio(rec)
        flags = _marks(line.rsplit(" | ", 1)[-1], _pick(rec, "name", "title"), printed, rejected)
        print(line + (" | " + " | ".join(flags) if flags else ""))


def unstop(printed, rejected):
    r = requests.get(UNSTOP_API, params={"opportunity": "hackathons", "per_page": 10,
                                         "oppstatus": "open", "searchTerm": "AI"},
                     headers={**web_text.HEADERS, "Accept": "application/json"}, timeout=25)
    r.raise_for_status()
    data = r.json().get("data") or []
    if isinstance(data, dict):
        data = data.get("data") or []
    print(f"Unstop: {len(data)} open hackathons matching 'AI'")
    if data:
        print("  keys: " + ", ".join(sorted(data[0])))
    for rec in data:
        line = format_unstop(rec)
        flags = _marks(line.rsplit(" | ", 1)[-1], _pick(rec, "title", "name"), printed, rejected)
        print(line + (" | " + " | ".join(flags) if flags else ""))


def platforms():
    printed, rejected = history()
    for label, read in (("lablab.ai", lablab), ("Devpost newest", devpost_newest),
                        ("Devfolio", devfolio), ("Unstop", unstop)):
        print(f"\n## {label}")
        try:
            read(printed, rejected)
        except Exception as e:  # noqa: BLE001 - one platform failing must not hide the others
            print(f"!! {label}: {type(e).__name__}: {str(e)[:200]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("devpost")
    d.add_argument("--pages", type=int, default=10)
    d.add_argument("--all", action="store_true", help="include no-cash and small-prize events")
    c = sub.add_parser("check")
    c.add_argument("urls", nargs="+")
    sub.add_parser("recheck")
    sub.add_parser("platforms")
    args = ap.parse_args()
    if args.cmd == "devpost":
        devpost(args.pages, args.all)
    elif args.cmd == "check":
        check(args.urls)
    elif args.cmd == "platforms":
        platforms()
    else:
        recheck()


if __name__ == "__main__":
    main()
