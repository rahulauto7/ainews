"""
Email rahul the AI hackathons rahul can actually enter and win cash in.

rahul, 2026-10-03: "make a scheduler who check popular hackathon sites for the
moment hackathon launched it will email me" (at rahularebhai@gmail.com). It runs
hourly from GitHub Actions (.github/workflows/hackathon_alerts.yml), not from a
Claude session: Claude cloud sessions in this project get linked to rahul's
computer, and a linked session cannot sign in to Gmail (found 2026-10-03).

rahul, 2026-10-12: "Only give me cash-based price hackathons ... more than
$5,000 in prizes. And online hackathons and check eligibility as well before
sending mail, like Indian working professional in IOCL ... the price is given
with priorities, with the highest price first ... make sure that when you send
it, I can sign up, and that the registration date is not in the past."

Each run reads the platforms in hackathon_sources.py (all but HackerEarth,
which refuses GitHub's servers; see NOT_FROM_GITHUB). A listing goes on to a
page check when it is an AI hackathon, not invite-only, its
sign-up has not closed, its submission deadline leaves 7+ days to build (or is
not listed), and its listed prize is not known to be under $5,000. The page
check (hackathon_check.py) reads the event's own page and rules for the cash
prize, an online format (or, for an in-person or hybrid event, the organiser
paying the travel: rahul, later on 2026-10-12, "It may be hybrid, but
sponsorships ... will be required, like flight, visa"), an open sign-up and who may enter (an Indian citizen
working at state-owned IOCL). Only events that pass are emailed, biggest cash
prize first, each once; the seen-list is a JSON file the workflow keeps on the
`hackathon-alerts-state` branch. A rejection is remembered for a week, so the
same page is not re-read every hour; a page that could not be read is tried
again next run.

A state file from before these checks (version 1) is replaced, and that run
emails every hackathon that passes now. A platform that cannot be read for a
day gets one email saying so, and another when it is back.

Usage:
  python3 tools/hackathon_watch.py --state PATH [--to EMAIL] [--dry-run]

--to defaults to HACKATHON_ALERT_EMAIL. Mail goes through the Gmail API with the
token JSON in GMAIL_TOKEN_JSON (the secret send_edition.yml uses too) or in
token.json, refreshed with plain HTTPS. --dry-run prints each email instead of
sending it and leaves the state file alone.

Exits 1 when every platform failed or an email could not be sent. Events are
recorded only after their email went out, so a failed send is retried next run.
"""

import argparse
import base64
import html
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hackathon_check as hc
import hackathon_sources as hs

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GMAIL_SEND = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
STATE_VERSION = 2
# Seen events are forgotten this long after their deadline; by then no listing
# shows them as open, so they cannot come back as "new".
FORGET_AFTER_DAYS = 30
# A platform unreadable for this long gets one email; a blip does not.
WARN_AFTER_HOURS = 24
# A rejected event's page is read again after this long (rules and prizes change).
RECHECK_AFTER_DAYS = 7
# Pages read per run, biggest listed prize first; the rest wait for the next run.
MAX_CHECKS_PER_RUN = 60
CHECK_WORKERS = 8

# Platforms that refuse GitHub's servers. HackerEarth's event feed answers 403
# to every GitHub Actions runner (first dry run, 2026-10-03) while answering a
# Claude cloud session fine, and its listing page renders in the browser, so
# there is nothing else to read. It stays in the daily PDF's candidate list.
NOT_FROM_GITHUB = {"HackerEarth"}
WATCHED = tuple((name, read) for name, read in hs.PLATFORMS if name not in NOT_FROM_GITHUB)


# ── State ────────────────────────────────────────────────────────────────────

def empty_state():
    return {"version": STATE_VERSION, "platforms": {}, "seen": {}, "checked": {}, "failing": {}}


def load_state(path):
    """The saved state, or a fresh one when there is none or it predates the
    cash and eligibility checks (its seen-list holds events rahul never wanted)."""
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        return empty_state()
    if state.get("version") != STATE_VERSION:
        return empty_state()
    return {**empty_state(), **state}


def save_state(path, state):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write("\n")


def name_key(name):
    """A hackathon's name reduced to letters and digits, to spot the same event
    listed on two platforms. Short generic names ("AI Hack") are not compared."""
    key = re.sub(r"[^a-z0-9]+", "", (name or "").lower())
    return key if len(key) >= 10 else None


def _same_event(deadline, other):
    """Two listings of one name are one event when their deadlines are within
    three days (platforms round differently) or either deadline is unknown.
    Two colleges' "Agentic AI Hackathon" a month apart stay separate."""
    if deadline is None or other is None:
        return True
    return abs((deadline - other).days) <= 3


# ── Deciding what to email ───────────────────────────────────────────────────

def listing_problem(e, today):
    """Why the listing alone rules an event out, or "" to read its page."""
    if not e["ai"]:
        return "not AI"
    if e["restricted"]:
        return e["restricted"]
    if e["deadline"] is not None and not hs.has_build_time(e["deadline"], today):
        return f"under {hs.MIN_BUILD_DAYS} days to build"
    if e.get("reg_closes") and e["reg_closes"] < today:
        return "registration closed"
    listed = hs.prize_usd(e["prize"])
    # Devpost's listed figure counts swag and credits too, so it is never below the cash.
    if listed and listed < hc.MIN_CASH_USD:
        return f"prize under ${hc.MIN_CASH_USD:,}"
    return ""


def candidates(events, errors, state, today):
    """Events whose page should be read this run, biggest listed prize first:
    not seen, not the same event as one seen, not rejected in the last week."""
    seen, checked = state["seen"], state["checked"]
    names = {}
    for v in seen.values():
        nk = name_key(v.get("name"))
        if nk:
            names.setdefault(nk, []).append(date.fromisoformat(v["deadline"]) if v.get("deadline") else None)
    recheck = (today - timedelta(days=RECHECK_AFTER_DAYS)).isoformat()
    out = []
    for e in sorted(events, key=lambda e: (-hs.prize_usd(e["prize"]), e["deadline"] or date.max, e["key"])):
        if e["platform"] in errors or listing_problem(e, today):
            continue
        nk = name_key(e["name"])
        if e["key"] in seen or any(_same_event(e["deadline"], d) for d in names.get(nk, [])):
            continue
        if checked.get(e["key"], {}).get("date", "") > recheck:
            continue
        if nk:
            names.setdefault(nk, []).append(e["deadline"])
        out.append(e)
    return out


def check_pages(events, today, fetch=hc.page_text):
    """Read each event's page and run hackathon_check.check on it.

    Returns (passed, rejected, unreadable): passed is [(event, result)],
    rejected {key: result}, unreadable {key: "error"}."""
    def one(e):
        try:
            return e, hc.check(e, fetch(e), today), None
        except Exception as exc:  # noqa: BLE001 - one page failing never hides the others
            return e, None, f"{type(exc).__name__}: {str(exc)[:150]}"

    passed, rejected, unreadable = [], {}, {}
    if not events:
        return passed, rejected, unreadable
    with ThreadPoolExecutor(max_workers=min(CHECK_WORKERS, len(events))) as ex:
        for e, result, err in ex.map(one, events):
            if err:
                unreadable[e["key"]] = err
            elif result["ok"]:
                passed.append((e, result))
            else:
                rejected[e["key"]] = result
    return passed, rejected, unreadable


def record(state, passed, today):
    for e, result in passed:
        state["seen"][e["key"]] = {"name": e["name"], "platform": e["platform"], "url": e["url"],
                                   "first_seen": today.isoformat(), "cash_usd": round(result["cash_usd"]),
                                   "deadline": e["deadline"].isoformat() if e["deadline"] else None}
        state["checked"].pop(e["key"], None)


def remember_rejections(state, events, rejected, today):
    by_key = {e["key"]: e for e in events}
    for key, result in rejected.items():
        state["checked"][key] = {"name": by_key[key]["name"], "date": today.isoformat(),
                                 "reasons": [r[:240] for r in result["reasons"]]}


def forget_expired(state, today):
    cutoff = (today - timedelta(days=FORGET_AFTER_DAYS)).isoformat()
    for key in [k for k, v in state["seen"].items() if v.get("deadline") and v["deadline"] < cutoff]:
        del state["seen"][key]
    for key in [k for k, v in state["checked"].items() if v.get("date", "") < cutoff]:
        del state["checked"][key]


def platform_health(state, errors, ok_platforms, now):
    """Update state["failing"]; return (newly_down, back_up) for the emails.

    newly_down  platforms failing for WARN_AFTER_HOURS that have not been reported
    back_up     platforms that were reported down and answered this run
    """
    failing = state["failing"]
    back_up = [p for p in ok_platforms if failing.get(p, {}).get("warned")]
    for p in ok_platforms:
        failing.pop(p, None)
    newly_down = []
    for p, err in errors.items():
        entry = failing.setdefault(p, {"since": now.isoformat(), "warned": False})
        entry["error"] = err[:200]
        since = datetime.fromisoformat(entry["since"])
        if not entry["warned"] and now - since >= timedelta(hours=WARN_AFTER_HOURS):
            newly_down.append((p, entry))
    return newly_down, back_up


# ── The emails ───────────────────────────────────────────────────────────────

def money(usd):
    return f"${usd:,.0f}"


def _due_text(e, today):
    if not e["deadline"]:
        return "Submission deadline not listed, check the page"
    days = hs.days_to_build(e["deadline"], today)
    what = "Submissions close" if e["deadline_kind"] == "submission" else "Ends"
    return f"{what} {e['deadline']:%a %d %b %Y} ({days} days to build)"


def _signup_text(e, result):
    reg = result.get("reg_closes")
    return f"Sign up by {reg:%a %d %b %Y}" if reg else "Sign-up open now (no closing date listed)"


def _by_cash(passed):
    return sorted(passed, key=lambda p: (-p[1]["cash_usd"], p[0]["deadline"] or date.max, p[0]["name"]))


def _lines(e, result, today):
    prize = f"Cash prizes about {money(result['cash_usd'])}"
    if e["prize"] and hs.prize_usd(e["prize"]) != result["cash_usd"]:
        prize += f" (listed: {e['prize']})"
    lines = [prize, _due_text(e, today), _signup_text(e, result)]
    if result.get("in_person"):
        where = f" ({e['where']})" if e.get("where") and e["where"].lower() not in ("online", e["platform"].lower()) else ""
        lines.append(f"In person or hybrid{where}. Travel paid: \"{result['travel']}\"")
        lines.append(f"Visa help: \"{result['visa']}\"" if result.get("visa") else "Visa help: not mentioned, ask the organiser")
    lines.append(f"Who can enter: {result['who']}" if result.get("who")
                 else "Who can enter: the page sets no limit we could find, check the rules")
    return lines


def event_text(e, result, today):
    return "\n".join([f"{e['name']} ({e['platform']})"] + [f"  {l}" for l in _lines(e, result, today)]
                     + [f"  {e['url']}"])


def event_html(e, result, today):
    rows = "".join(f'<div style="font-size:13px;color:#333;margin-top:3px;">{html.escape(l)}</div>'
                   for l in _lines(e, result, today))
    return (f'<tr><td style="padding:10px 0;border-bottom:1px solid #e5e5e5;">'
            f'<a href="{html.escape(e["url"], quote=True)}" style="font-size:15px;font-weight:bold;'
            f'color:#1a4fd6;text-decoration:none;">{html.escape(e["name"])}</a>'
            f'<span style="font-size:12px;color:#777;"> &middot; {html.escape(e["platform"])}</span>'
            f'{rows}</td></tr>')


def _page(intro_html, rows_html, footer):
    return f"""<div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;">
<div style="background:#1a1a2e;padding:16px 20px;"><span style="color:#fff;font-size:18px;font-weight:bold;">
AI Hackathon Alerts</span></div>
<div style="padding:16px 20px;background:#f8f9fa;">{intro_html}
<table style="border-collapse:collapse;width:100%;">{rows_html}</table>
<p style="color:#888;font-size:12px;margin-top:20px;">{footer}</p></div></div>"""


FOOTER = (f"Checked every hour on {len(WATCHED)} sites: "
          + ", ".join(name if name != "mlcontests" else "mlcontests.com (Kaggle, DrivenData, CodaLab"
                      " and more)" for name, _ in WATCHED)
          + f". Only AI hackathons that are online, or in person / hybrid with travel paid by the organiser, "
          f"with at least {money(hc.MIN_CASH_USD)} in cash prizes, sign-up "
          f"still open, {hs.MIN_BUILD_DAYS}+ days before the submission deadline, and rules that let an "
          "Indian working professional at a state-owned company enter (no students-only, country-limited "
          "or government-staff-excluded events). Eligibility is read from each event's own page; confirm "
          "it in the official rules before you submit.")


def alert_email(passed, today, first=False):
    """(subject, text, html) listing the events that passed, biggest cash first."""
    passed = _by_cash(passed)
    top_e, top = passed[0]
    if len(passed) == 1:
        subject = f"AI hackathon, {money(top['cash_usd'])} cash: {top_e['name'][:80]}"
        intro = "A new AI hackathon you can enter:"
    else:
        subject = f"{len(passed)} AI hackathons you can enter, up to {money(top['cash_usd'])} cash"
        intro = f"{len(passed)} new AI hackathons you can enter, biggest cash prize first:"
    if first:
        subject = f"Hackathon alerts, now cash and eligibility checked: {len(passed)} open"
        intro = ("From now on you only get AI hackathons with real cash prizes that you can sign up for and "
                 "enter, online or with travel paid. These {len(passed)} pass today, biggest cash prize first:")
    text = intro + "\n\n" + "\n\n".join(event_text(e, r, today) for e, r in passed) + "\n\n" + FOOTER
    body = _page(f'<p style="font-size:14px;color:#333;">{intro}</p>',
                 "".join(event_html(e, r, today) for e, r in passed), FOOTER)
    return subject, text, body


def health_email(newly_down, back_up):
    lines = []
    for p, entry in newly_down:
        lines.append(f"{p} could not be read since {entry['since'][:16].replace('T', ' ')} UTC "
                     f"({entry.get('error', '')}). New hackathons there are not being caught.")
    for p in back_up:
        lines.append(f"{p} can be read again; alerts from it have resumed.")
    subject = ("Hackathon alerts: " + ", ".join(p for p, _ in newly_down) + " unreadable" if newly_down
               else "Hackathon alerts: " + ", ".join(back_up) + " back")
    text = "\n\n".join(lines)
    body = _page("".join(f'<p style="font-size:14px;color:#333;">{html.escape(l)}</p>' for l in lines),
                 "", FOOTER)
    return subject, text, body


# ── Sending ──────────────────────────────────────────────────────────────────

def gmail_token():
    raw = os.environ.get("GMAIL_TOKEN_JSON")
    if not raw:
        path = os.path.join(PROJECT_ROOT, "token.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                raw = f.read()
    if not raw:
        raise RuntimeError("no Gmail token: set GMAIL_TOKEN_JSON or provide token.json")
    return json.loads(raw)


def gmail_send(to, subject, text, body, token=None):
    """Send one email through the Gmail API, refreshing the access token first."""
    token = token or gmail_token()
    r = requests.post(token.get("token_uri") or "https://oauth2.googleapis.com/token", timeout=30, data={
        "client_id": token["client_id"], "client_secret": token["client_secret"],
        "refresh_token": token["refresh_token"], "grant_type": "refresh_token"})
    if r.status_code != 200:
        raise RuntimeError(f"Gmail token refresh failed: HTTP {r.status_code} {r.text[:200]}")
    msg = MIMEMultipart("alternative")
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(body, "html", "utf-8"))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    r = requests.post(GMAIL_SEND, headers={"Authorization": f"Bearer {r.json()['access_token']}"},
                      json={"raw": raw}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Gmail send failed: HTTP {r.status_code} {r.text[:200]}")


# ── One run ──────────────────────────────────────────────────────────────────

def run(state_path, to=None, dry_run=False, now=None, collect=hs.collect, send=gmail_send, fetch=hc.page_text):
    now = now or datetime.now(timezone.utc)
    today = hs.today_ist(now)
    state = load_state(state_path)
    first_run = not state["platforms"]

    events, errors = collect(today, WATCHED)
    ok_platforms = [name for name, _ in WATCHED if name not in errors]
    for name, err in errors.items():
        print(f"::warning::{name} could not be read: {err}")
    counts = {}
    for e in events:
        counts[e["platform"]] = counts.get(e["platform"], 0) + 1
    print("Read: " + ", ".join(f"{p} {counts.get(p, 0)}" for p in ok_platforms)
          + (f" | failed: {', '.join(errors)}" if errors else ""))
    if not ok_platforms:
        print("Every platform failed; nothing recorded.")
        return 1

    todo = candidates(events, errors, state, today)
    waiting = todo[MAX_CHECKS_PER_RUN:]
    todo = todo[:MAX_CHECKS_PER_RUN]
    passed, rejected, unreadable = check_pages(todo, today, fetch)
    by_key = {e["key"]: e for e in todo}
    print(f"Pages checked: {len(todo)} (left for next run: {len(waiting)}) | pass: {len(passed)} | "
          f"rejected: {len(rejected)} | unreadable: {len(unreadable)}" + (" | first run" if first_run else ""))
    for e, r in _by_cash(passed):
        print(f"  PASS {money(r['cash_usd'])} {e['name']} ({e['platform']})")
    for key, r in rejected.items():
        print(f"  no   {by_key[key]['name']} ({by_key[key]['platform']}): {'; '.join(r['reasons'])[:200]}")
    for key, err in unreadable.items():
        print(f"  ??   {by_key[key]['name']} ({by_key[key]['platform']}): {err}")

    newly_down, back_up = platform_health(state, errors, ok_platforms, now)
    emails = []
    if passed:
        emails.append(("alert", alert_email(passed, today, first=first_run)))
    if newly_down or back_up:
        emails.append(("health", health_email(newly_down, back_up)))

    for kind, (subject, text, body) in emails:
        if dry_run:
            print(f"\n--- {kind} email (dry run, not sent) ---\nSubject: {subject}\n\n{text}\n")
            continue
        try:
            send(to, subject, text, body)
        except Exception as exc:  # noqa: BLE001 - nothing is recorded, so the next run retries
            print(f"::error::{kind} email not sent: {type(exc).__name__}: {exc}")
            return 1
        print(f"Sent {kind} email: {subject}")

    if dry_run:
        return 0
    record(state, passed, today)
    remember_rejections(state, todo, rejected, today)
    for p, entry in newly_down:
        entry["warned"] = True
    for p in ok_platforms:
        state["platforms"].setdefault(p, today.isoformat())
    forget_expired(state, today)
    save_state(state_path, state)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", required=True, help="the seen-list JSON (created if missing)")
    ap.add_argument("--to", default=os.environ.get("HACKATHON_ALERT_EMAIL"))
    ap.add_argument("--dry-run", action="store_true", help="print the emails; send nothing, save nothing")
    args = ap.parse_args()
    if not args.dry_run and not args.to:
        print("::error::no recipient: pass --to or set HACKATHON_ALERT_EMAIL")
        return 1
    return run(args.state, to=args.to, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
