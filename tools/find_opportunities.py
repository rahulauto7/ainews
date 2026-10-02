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
"""

import argparse
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import web_text
from builder_helpers import OPPORTUNITY_KEYS, prior_editions
from fetch_articles import fetch_one

DEVPOST_API = "https://devpost.com/api/hackathons"

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


def devpost(pages, show_all=False):
    printed, rejected = history()
    rows, total = [], None
    for page in range(1, pages + 1):
        r = requests.get(DEVPOST_API, headers={**web_text.HEADERS, "Accept": "application/json"},
                         params={"status[]": ["open", "upcoming"], "themes[]": "Machine Learning/AI",
                                 "order_by": "prize-amount", "page": page}, timeout=25)
        r.raise_for_status()
        data = r.json()
        total = data.get("meta", {}).get("total_count")
        rows += data.get("hackathons", [])
        if not data.get("hackathons") or (total and len(rows) >= total):
            break

    for h in rows:
        h["_prize"] = re.sub(r"<[^>]+>", "", h.get("prize_amount") or "") or "-"
        h["_cash"] = (h.get("prizes_counts") or {}).get("cash", 0)
    shown = [h for h in rows if show_all or (h["_cash"] and _usd(h["_prize"]) >= MIN_USD)]
    shown.sort(key=lambda h: -_usd(h["_prize"]))

    print(f"Devpost: {len(rows)} of {total} open/upcoming Machine Learning/AI hackathons; "
          f"{len(rows) - len(shown)} hidden (no cash prize or under ~${MIN_USD:,}; --all shows them)")
    print("Prize figures include non-cash value; confirm cash on the /rules page before publishing.")
    for h in shown:
        prize, cash = h["_prize"], h["_cash"]
        flags = []
        if not cash:
            flags.append("NO CASH PRIZES")
        if h.get("invite_only"):
            flags.append("INVITE-ONLY " + (h.get("eligibility_requirement_invite_only_description") or "")[:60])
        seen = printed.get(_norm_url(h["url"]))
        if seen:
            flags.append("printed " + ",".join(sorted(set(seen))))
        rej = rejected.get(h["title"].lower())
        if rej:
            flags.append(f"rejected {rej[0][5:]}: {rej[1][:60]}")
        where = (h.get("displayed_location") or {}).get("location", "")
        print(f"- {prize:>10} ({cash} cash) | {h['title'][:70]} | {h.get('submission_period_dates')} "
              f"({h.get('time_left_to_submission')}) | {where[:20]} | {h['url']}"
              + (" | " + " | ".join(flags) if flags else ""))


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


def check(urls):
    decoded = web_text.load_decoded_cache()
    jobs = []
    for url in urls:
        jobs.append(url)
        if urlparse(url).netloc.endswith(".devpost.com"):
            jobs.append(url.rstrip("/") + "/rules")
    with ThreadPoolExecutor(max_workers=6) as ex:
        recs = dict(zip(jobs, ex.map(lambda u: fetch_one(u, decoded), jobs)))
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("devpost")
    d.add_argument("--pages", type=int, default=10)
    d.add_argument("--all", action="store_true", help="include no-cash and small-prize events")
    c = sub.add_parser("check")
    c.add_argument("urls", nargs="+")
    sub.add_parser("recheck")
    args = ap.parse_args()
    if args.cmd == "devpost":
        devpost(args.pages, args.all)
    elif args.cmd == "check":
        check(args.urls)
    else:
        recheck()


if __name__ == "__main__":
    main()
