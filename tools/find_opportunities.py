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
      New AI hackathons from every other platform, one block each: lablab.ai
      (open events, soonest end first, each event page checked), Devpost's
      newest "AI" events that the theme listing above does not show, then
      mlcontests.com (Kaggle, AIcrowd, DrivenData, Zindi, ...), HackerEarth,
      Devfolio, Unstop, MLH, TAIKAI and Hackster, each biggest prize first
      (hackathon_sources.prize_usd). One platform failing prints
      "!! <platform>: <error>" and the others still print. prep_run.py writes
      this to .tmp/hackathons.txt.

Every hackathon listing applies the 7-day build rule (rahul, 2026-10-03): an
event whose submission deadline is under MIN_BUILD_DAYS away is hidden and
counted, and `recheck` marks a carried-forward hackathon that has fallen under
it. Registration deadlines never count. The readers live in hackathon_sources.py,
shared with the hourly new-hackathon email (hackathon_watch.py).
"""

import argparse
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hackathon_sources as hs
import web_text
from builder_helpers import OPPORTUNITY_KEYS, prior_editions
from fetch_articles import fetch_one
from hackathon_sources import DEVPOST_THEME, MIN_BUILD_DAYS, parse_lablab_listing  # noqa: F401 - re-exported

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


# Devpost events below this (hs.prize_usd, a rough conversion) are hidden.
MIN_USD = 1000


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
    h["_due"] = hs.devpost_deadline(h.get("submission_period_dates"))
    return h


def _devpost_line(h, printed, rejected):
    prize, cash = h["_prize"], h["_cash"]
    flags = []
    if not h["_due"]:
        flags.append("NO SUBMISSION DATE - confirm on the page")
    if not cash:
        flags.append("NO CASH PRIZES")
    if h.get("invite_only"):
        flags.append("INVITE-ONLY " + (h.get("eligibility_requirement_invite_only_description") or "")[:60])
    flags += _marks(h["url"], h["title"], printed, rejected)
    where = (h.get("displayed_location") or {}).get("location", "")
    left = f"{(h['_due'] - hs.today_ist()).days}d to build" if h["_due"] else h.get("time_left_to_submission")
    return (f"- {prize:>10} ({cash} cash) | {h['title'][:70]} | {h.get('submission_period_dates')} "
            f"({left}) | {where[:20]} | {h['url']}"
            + (" | " + " | ".join(flags) if flags else ""))


def _devpost_rows(params, pages):
    rows, total = hs.devpost_rows(params, pages)
    return [_devpost_fields(h) for h in rows], total


def _too_soon(due, today):
    """True when a known submission deadline leaves under MIN_BUILD_DAYS to build."""
    return due is not None and not hs.has_build_time(due, today)


def devpost(pages, show_all=False):
    printed, rejected = history()
    today = hs.today_ist()
    rows, total = _devpost_rows({"status[]": ["open", "upcoming"], "themes[]": DEVPOST_THEME,
                                 "order_by": "prize-amount"}, pages)
    soon = [h for h in rows if _too_soon(h["_due"], today)]
    rows_ok = [h for h in rows if not _too_soon(h["_due"], today)]
    shown = [h for h in rows_ok if show_all or (h["_cash"] and hs.prize_usd(h["_prize"]) >= MIN_USD)]
    shown.sort(key=lambda h: -hs.prize_usd(h["_prize"]))

    print(f"Devpost: {len(rows)} of {total} open/upcoming Machine Learning/AI hackathons; "
          f"{len(soon)} hidden (submissions close in under {MIN_BUILD_DAYS} days), "
          f"{len(rows_ok) - len(shown)} hidden (no cash prize or under ~${MIN_USD:,}; --all shows them)")
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
    today = hs.today_ist()
    for date, edition in prior_editions():
        for key in OPPORTUNITY_KEYS:
            for s in edition.get("sections", {}).get(key, []):
                u = s.get("url")
                if u and _norm_url(u) not in seen:
                    seen.add(_norm_url(u))
                    urls.append(u)
                    flag = ""
                    if key == "ai_hackathons":
                        due = hs.parse_deadline(s.get("deadline"), today)
                        days = hs.days_to_build(due, today)
                        flag = (" | NO SUBMISSION DATE - confirm before carrying" if days is None else
                                f" | UNDER {MIN_BUILD_DAYS} DAYS ({days}d) - drop" if days < MIN_BUILD_DAYS
                                else f" | {days}d to build")
                    print(f"[{date[5:]}] {'hackathon' if key == 'ai_hackathons' else 'programme'}: "
                          f"{s['title'][:80]} | deadline printed: {s.get('deadline', '-')}{flag}")
    print()
    check(urls)


# ── New hackathons from other platforms (`platforms`) ────────────────────────

def lablab(printed, rejected):
    """Open lablab.ai hackathons with 7+ days to build, each followed by what its
    own page says about prize, eligibility and deadline. Prize lines often mix
    cash and credits ("$5k cash + $5k credits"), so the event page decides."""
    html, _ = web_text.fetch_html(hs.LABLAB_LISTING)
    today = hs.today_ist()
    listing = parse_lablab_listing(html, datetime.now(timezone.utc))
    events = [e for e in listing if hs.has_build_time(hs.ist_date(e["end_at"]), today)]
    print(f"lablab.ai: {len(events)} open hackathons with {MIN_BUILD_DAYS}+ days to build, soonest end "
          f"first; {len(listing) - len(events)} hidden (end in under {MIN_BUILD_DAYS} days)")
    urls = [f"https://lablab.ai/ai-hackathons/{e['slug']}" for e in events]
    recs = _fetch_pages(urls)
    for event, url in zip(events, urls):
        rec = recs[url]
        name = event["name"]
        flags = ([] if event["signup"] else ["SIGNUP CLOSED"]) + _marks(url, name, printed, rejected)
        days = hs.days_to_build(hs.ist_date(event["end_at"]), today)
        print(f"- {name[:70]} | {event['start']} to {event['end']} ({days}d to build) | {url}"
              + (" | " + " | ".join(flags) if flags else ""))
        print("\n".join(_report(url, rec).splitlines()[1:]))


def devpost_newest(printed, rejected, pages=3):
    """Devpost's newest open "AI" events in any theme: the ones the theme listing misses."""
    today = hs.today_ist()
    rows, total = _devpost_rows({"status[]": ["open", "upcoming"], "search": "AI",
                                 "order_by": "recently-added"}, pages)
    new = [h for h in rows
           if DEVPOST_THEME not in {t.get("name") for t in h.get("themes") or []}]
    soon = [h for h in new if _too_soon(h["_due"], today)]
    new.sort(key=lambda h: -hs.prize_usd(h["_prize"]))
    print(f"Devpost newest: {len(rows)} of {total} open/upcoming matching 'AI', biggest prize first; "
          f"{len(new)} are outside the {DEVPOST_THEME} theme listing, {len(soon)} of them hidden "
          f"(submissions close in under {MIN_BUILD_DAYS} days)")
    for h in new:
        if h not in soon:
            print(_devpost_line(h, printed, rejected))


def event_line(e, today, printed, rejected):
    """One hackathon from hackathon_sources as a line, with its build time."""
    days = hs.days_to_build(e["deadline"], today)
    due = (f"{'submissions close' if e['deadline_kind'] == 'submission' else 'ends'} "
           f"{e['deadline']:%d %b %Y} ({days}d to build)" if e["deadline"] else "deadline not listed")
    flags = ([e["restricted"].upper()] if e["restricted"] else []) + _marks(e["url"], e["name"], printed, rejected)
    return (f"- {(e['prize'] or '-')[:40]:>10} | {e['name'][:70]} | {due} | {e['where'][:30]} | {e['url']}"
            + (" | " + " | ".join(flags) if flags else ""))


def platform_block(name, read, printed, rejected):
    """Print one hackathon_sources platform: AI events with 7+ days to build,
    biggest prize first (then soonest deadline), and a count of what was hidden
    and why."""
    today = hs.today_ist()
    events = read(today)
    ai = [e for e in events if e["ai"]]
    soon = [e for e in ai if _too_soon(e["deadline"], today)]
    shown = sorted((e for e in ai if e not in soon),
                   key=lambda e: (-hs.prize_usd(e["prize"]), e["deadline"] is None, e["deadline"]))
    print(f"{name}: {len(shown)} open AI hackathons with {MIN_BUILD_DAYS}+ days to build; hidden: "
          f"{len(events) - len(ai)} not about AI, {len(soon)} closing in under {MIN_BUILD_DAYS} days")
    for e in shown:
        print(event_line(e, today, printed, rejected))


OTHER_PLATFORMS = tuple((name, read) for name, read in hs.PLATFORMS
                        if name not in ("Devpost", "lablab.ai"))


def platforms():
    printed, rejected = history()
    today = hs.today_ist()
    print(f"Build-time rule: AI hackathons whose submission deadline is {MIN_BUILD_DAYS}+ days away, "
          f"on or after {today + timedelta(days=MIN_BUILD_DAYS):%d %b %Y}. "
          "Registration deadlines do not count. 'ends' = the platform gives only the event's end.")
    blocks = [("lablab.ai", lablab), ("Devpost newest", devpost_newest)]
    blocks += [(name, lambda p, r, read=read, name=name: platform_block(name, read, p, r))
               for name, read in OTHER_PLATFORMS]
    for label, read in blocks:
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
