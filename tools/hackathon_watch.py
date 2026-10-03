"""
Email rahul as soon as a new AI hackathon appears on any platform.

rahul, 2026-10-03: "make a scheduler who check popular hackathon sites for the
moment hackathon launched it will email me" (at rahularebhai@gmail.com). It runs
hourly from GitHub Actions (.github/workflows/hackathon_alerts.yml), not from a
Claude session: Claude cloud sessions in this project get linked to rahul's
computer, and a linked session cannot sign in to Gmail (found 2026-10-03).

Each run reads every platform in hackathon_sources.py and keeps the AI
hackathons that anyone can enter and whose submission deadline leaves 7+ days
to build - the daily section's rule. An event that lists no deadline is kept and
marked, because a missed hackathon costs more than a check. Events not seen
before are emailed; the seen-list is a JSON file the workflow keeps on the
`hackathon-alerts-state` branch.

The first time a platform is read successfully its whole listing is recorded
without an alert, or the first run (and every platform added later) would mail
each open event as "new". The very first run instead sends one welcome email
listing everything open now. A platform that cannot be read for a day gets one
email saying so, and another when it is back.

Usage:
  python3 tools/hackathon_watch.py --state PATH [--to EMAIL] [--dry-run]

--to defaults to HACKATHON_ALERT_EMAIL. Mail goes through the Gmail API with the
token JSON in GMAIL_TOKEN_JSON (the secret send_edition.yml uses too) or in
token.json, refreshed with plain HTTPS, so the workflow needs only requests.
--dry-run prints each email instead of sending it and leaves the state file
alone.

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
from datetime import date, datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hackathon_sources as hs

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GMAIL_SEND = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
# Seen events are forgotten this long after their deadline; by then no listing
# shows them as open, so they cannot come back as "new".
FORGET_AFTER_DAYS = 30
# A platform unreadable for this long gets one email; a blip does not.
WARN_AFTER_HOURS = 24


# ── State ────────────────────────────────────────────────────────────────────

def empty_state():
    return {"version": 1, "platforms": {}, "seen": {}, "failing": {}}


def load_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
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


# ── Deciding what is new ─────────────────────────────────────────────────────

def worth_alerting(e, today):
    """An AI hackathon anyone can enter, with 7+ days to build or no deadline listed."""
    return (e["ai"] and not e["restricted"]
            and (e["deadline"] is None or hs.has_build_time(e["deadline"], today)))


def plan(events, errors, state, today):
    """Split this run's events into (new, seeded).

    new     events to email: not seen before, on a platform read successfully
            before this run.
    seeded  events on a platform read successfully for the first time; recorded
            silently (or listed in the welcome email on the very first run).
    """
    seen = state["seen"]
    names = {}
    for v in seen.values():
        nk = name_key(v.get("name"))
        if nk:
            names.setdefault(nk, []).append(date.fromisoformat(v["deadline"]) if v.get("deadline") else None)
    new, seeded = [], []
    order = [name for name, _ in hs.PLATFORMS]
    for e in sorted(events, key=lambda e: order.index(e["platform"]) if e["platform"] in order else 99):
        if e["platform"] in errors or not worth_alerting(e, today):
            continue
        nk = name_key(e["name"])
        if e["key"] in seen or any(_same_event(e["deadline"], d) for d in names.get(nk, [])):
            continue
        if nk:
            names.setdefault(nk, []).append(e["deadline"])
        (seeded if e["platform"] not in state["platforms"] else new).append(e)
    return new, seeded


def record(state, events, today):
    for e in events:
        state["seen"][e["key"]] = {"name": e["name"], "platform": e["platform"],
                                   "first_seen": today.isoformat(),
                                   "deadline": e["deadline"].isoformat() if e["deadline"] else None}


def forget_expired(state, today):
    cutoff = (today - timedelta(days=FORGET_AFTER_DAYS)).isoformat()
    for key in [k for k, v in state["seen"].items() if v.get("deadline") and v["deadline"] < cutoff]:
        del state["seen"][key]


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

def _due_text(e, today):
    if not e["deadline"]:
        return "Deadline not listed, check the page"
    days = hs.days_to_build(e["deadline"], today)
    what = "Submissions close" if e["deadline_kind"] == "submission" else "Ends"
    return f"{what} {e['deadline']:%a %d %b %Y} ({days} days to build)"


def _by_deadline(events):
    return sorted(events, key=lambda e: (e["deadline"] is None, e["deadline"] or date.max, e["name"]))


def event_text(e, today):
    lines = [f"{e['name']} ({e['platform']})", f"  {_due_text(e, today)}"]
    details = " | ".join(x for x in (e["prize"] and f"Prize: {e['prize']}", e["where"]) if x)
    if details:
        lines.append(f"  {details}")
    lines.append(f"  {e['url']}")
    return "\n".join(lines)


def event_html(e, today):
    details = " &middot; ".join(html.escape(x) for x in (e["prize"] and f"Prize: {e['prize']}", e["where"]) if x)
    return (f'<tr><td style="padding:10px 0;border-bottom:1px solid #e5e5e5;">'
            f'<a href="{html.escape(e["url"], quote=True)}" style="font-size:15px;font-weight:bold;'
            f'color:#1a4fd6;text-decoration:none;">{html.escape(e["name"])}</a>'
            f'<div style="font-size:13px;color:#333;margin-top:3px;">{html.escape(_due_text(e, today))}</div>'
            f'<div style="font-size:12px;color:#777;margin-top:2px;">{html.escape(e["platform"])}'
            f'{" &middot; " + details if details else ""}</div></td></tr>')


def _page(intro_html, rows_html, footer):
    return f"""<div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;">
<div style="background:#1a1a2e;padding:16px 20px;"><span style="color:#fff;font-size:18px;font-weight:bold;">
AI Hackathon Alerts</span></div>
<div style="padding:16px 20px;background:#f8f9fa;">{intro_html}
<table style="border-collapse:collapse;width:100%;">{rows_html}</table>
<p style="color:#888;font-size:12px;margin-top:20px;">{footer}</p></div></div>"""


FOOTER = (f"Checked every hour on {len(hs.PLATFORMS)} platforms: "
          + ", ".join(name if name != "mlcontests" else "mlcontests.com (Kaggle, AIcrowd, DrivenData, Zindi"
                      " and more)" for name, _ in hs.PLATFORMS)
          + f". Only AI hackathons with {hs.MIN_BUILD_DAYS}+ days left before the submission deadline.")


def alert_email(new, today):
    """(subject, text, html) for newly announced hackathons."""
    new = _by_deadline(new)
    if len(new) == 1:
        e = new[0]
        verb = "closes" if e["deadline_kind"] == "submission" else "ends"
        when = f" ({verb} {e['deadline']:%d %b})" if e["deadline"] else ""
        subject = f"New AI hackathon: {e['name'][:80]}{when}"
        intro = "A new AI hackathon was just listed:"
    else:
        platforms = sorted({e["platform"] for e in new})
        subject = f"{len(new)} new AI hackathons on {', '.join(platforms)}"
        intro = f"{len(new)} new AI hackathons were just listed, soonest deadline first:"
    text = intro + "\n\n" + "\n\n".join(event_text(e, today) for e in new) + "\n\n" + FOOTER
    body = _page(f'<p style="font-size:14px;color:#333;">{intro}</p>',
                 "".join(event_html(e, today) for e in new), FOOTER)
    return subject, text, body


def welcome_email(seeded, today):
    seeded = _by_deadline(seeded)
    subject = f"Hackathon alerts are on: {len(seeded)} AI hackathons open now"
    intro = (f"From now on you get an email whenever a new AI hackathon is listed. "
             f"These {len(seeded)} are open today, soonest deadline first:")
    text = intro + "\n\n" + "\n\n".join(event_text(e, today) for e in seeded) + "\n\n" + FOOTER
    body = _page(f'<p style="font-size:14px;color:#333;">{intro}</p>',
                 "".join(event_html(e, today) for e in seeded), FOOTER)
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

def run(state_path, to=None, dry_run=False, now=None, collect=hs.collect, send=gmail_send):
    now = now or datetime.now(timezone.utc)
    today = hs.today_ist(now)
    state = load_state(state_path)
    first_run = not state["platforms"]

    events, errors = collect(today)
    ok_platforms = [name for name, _ in hs.PLATFORMS if name not in errors]
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

    new, seeded = plan(events, errors, state, today)
    newly_down, back_up = platform_health(state, errors, ok_platforms, now)
    print(f"New AI hackathons with {hs.MIN_BUILD_DAYS}+ days to build: {len(new)} | "
          f"first read of a platform, recorded quietly: {len(seeded)}"
          + (" (first run: welcome email)" if first_run else ""))

    emails = []
    if first_run and seeded:
        emails.append(("welcome", welcome_email(seeded, today)))
    if new:
        emails.append(("alert", alert_email(new, today)))
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
    record(state, new + seeded, today)
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
