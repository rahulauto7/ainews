"""Cases for hackathon_watch.py, the hourly hackathon email.

The watcher's job is narrow and easy to get wrong in both directions: miss a
hackathon rahul can enter, or mail one rahul cannot enter (too small a cash prize,
in person, sign-up closed, students only, not open to India) or the same one
twice. Each case below drives run() with a fake platform reader, a fake page
reader and a fake mailbox, so nothing touches the network.

Run: python3 tools/tests/test_hackathon_watch.py
"""

import contextlib
import io
import json
import os
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hackathon_sources as hs
import hackathon_watch as hw

NOW = datetime(2026, 10, 3, 6, 0, tzinfo=timezone.utc)   # 11:30 IST
TODAY = date(2026, 10, 3)
ALL = [name for name, _ in hw.WATCHED]
OPEN_PAGE = "An online hackathon, open to everyone worldwide."


def check(failures, cond, msg):
    if not cond:
        failures.append(msg)


def ev(platform, key, name, days, ai=True, restricted="", kind="submission", prize="$10,000", online=True,
       reg_closes=None):
    deadline = TODAY + timedelta(days=days) if days is not None else None
    return hs.event(platform, f"{platform.lower()}:{key}", name, f"https://{key}.example.com/", deadline,
                    kind, prize=prize, where="Online", ai=ai, restricted=restricted, online=online,
                    reg_closes=reg_closes)


class World:
    """The platforms' listings, the events' own pages and the mailbox, as one
    run sees them."""

    def __init__(self, events, errors=None, pages=None):
        self.events, self.errors, self.sent, self.fail_send = events, errors or {}, [], False
        self.pages, self.fetched = pages or {}, []

    def collect(self, today, platforms):
        names = {name for name, _ in platforms}
        return ([e for e in self.events if e["platform"] in names and e["platform"] not in self.errors],
                {p: err for p, err in self.errors.items() if p in names})

    def fetch(self, e):
        self.fetched.append(e["key"])
        # Devpost's listed prize counts swag too; its page states the cash.
        page = self.pages.get(e["key"], OPEN_PAGE + (f" {e['prize']} in cash." if e["prize"] else ""))
        if isinstance(page, Exception):
            raise page
        return page

    def send(self, to, subject, text, body):
        if self.fail_send:
            raise RuntimeError("HTTP 403")
        self.sent.append({"to": to, "subject": subject, "text": text, "html": body})


def run(world, state, now=NOW, dry_run=False):
    """One watcher run, its progress lines swallowed so a failure's FAIL lines
    are what verify_edition.py shows."""
    world.sent, world.fetched = [], []
    with contextlib.redirect_stdout(io.StringIO()):
        return hw.run(state, to="rahul@example.com", dry_run=dry_run, now=now,
                      collect=world.collect, send=world.send, fetch=world.fetch)


def main():
    failures, cases = [], 0
    tmp = tempfile.mkdtemp()
    state = os.path.join(tmp, "seen.json")

    base = [
        ev("Devpost", "qloo", "Qloo Agentic Hackathon", 27, prize="$25,000"),
        ev("lablab.ai", "amd", "AMD Developer Hackathon ACT III", 15, kind="end", prize="$10,000"),
        ev("mlcontests", "arc", "ARC Prize 2026 - ARC-AGI-3", 30, prize="$850,000"),
        ev("Devpost", "soon", "Closing Soon AI Hack", 6),                   # under 7 days to build
        ev("Devpost", "nonai", "Climate Data Jam", 20, ai=False),           # not AI
        ev("Devpost", "invite", "Invite Only AI Hack", 20, restricted="invite-only"),
        ev("Devfolio", "campus", "Campus AI Hack", 20, online=False),       # in person, no travel paid
        ev("Devfolio", "flyin", "Fly-in AI Summit Hack", 20, online=False, prize="$8,000"),  # travel paid
        ev("Unstop", "tiny", "Tiny Prize AI Sprint", 20, prize="₹50,000"),  # about $600
        ev("Devfolio", "regshut", "Sign-up Over AI Hack", 20, reg_closes=TODAY - timedelta(days=1)),
        ev("MLH", "uni", "University AI Hack", 20, prize=""),               # page: students only
        ev("TAIKAI", "us", "US Residents AI Challenge", 20, prize="20,000 USD"),  # page: US only
    ]
    pages = {"mlh:uni": "Online. This hackathon is open only to currently enrolled university students. "
                        "Prize pool: $20,000 in cash.",
             "taikai:us": "Online. The challenge is open only to legal residents of the United States.",
             "devfolio:campus": "Held at our campus in Pune. Open to all. Prizes worth $10,000.",
             "devfolio:flyin": "Held in Dubai. Open to all. Prize pool $8,000. Flights are covered for every "
                               "selected team. Visa assistance is provided."}
    world = World(list(base), pages=dict(pages))

    # ── 1. A dry run prints, sends nothing and writes nothing ────────────────
    cases += 2
    check(failures, run(world, state, dry_run=True) == 0, "dry run must exit 0")
    check(failures, not world.sent and not os.path.exists(state),
          "a dry run must not send mail or write the state file")

    # ── 2. First run: one email with every hackathon that passes, biggest cash first
    rc = run(world, state)
    cases += 6
    check(failures, rc == 0, f"first run exit code {rc}")
    check(failures, len(world.sent) == 1
          and world.sent[0]["subject"] == "Hackathon alerts, now cash and eligibility checked: 4 open",
          f"first run sends one email naming 4 hackathons: {[m['subject'] for m in world.sent]}")
    text = world.sent[0]["text"] if world.sent else ""
    for name in ("Closing Soon", "Climate Data", "Invite Only", "Campus", "Tiny Prize", "Sign-up Over",
                 "University", "US Residents"):
        check(failures, name not in text, f"{name} must not be mailed:\n{text}")
    cases += 7
    check(failures, text.index("ARC") < text.index("Qloo") < text.index("AMD"),
          "the email lists the biggest cash prize first")
    cases += 1
    check(failures, 'Travel paid: "Flights are covered for every selected team."' in text
          and 'Visa help: "Visa assistance is provided."' in text and "Campus" not in text,
          f"an in-person event is mailed only with paid travel, and says so:\n{text}")
    check(failures, "Cash prizes about $850,000" in text and "Sign-up open now" in text
          and "27 days to build" in text, f"each entry shows cash, sign-up and build time:\n{text}")
    check(failures, sorted(world.fetched) == ["devfolio:campus", "devfolio:flyin", "devpost:qloo", "lablab.ai:amd",
                                              "mlcontests:arc", "mlh:uni", "taikai:us"],
          f"only events the listing allows have their page read: {sorted(world.fetched)}")
    saved = json.load(open(state))
    check(failures, saved["version"] == hw.STATE_VERSION and sorted(saved["platforms"]) == sorted(ALL)
          and sorted(saved["seen"]) == ["devfolio:flyin", "devpost:qloo", "lablab.ai:amd", "mlcontests:arc"],
          f"state after the first run: platforms={sorted(saved['platforms'])} seen={sorted(saved['seen'])}")
    check(failures, saved["seen"].get("mlcontests:arc", {}).get("cash_usd") == 850_000,
          f"seen records keep the cash: {saved['seen'].get('mlcontests:arc')}")
    check(failures, sorted(saved["checked"]) == ["devfolio:campus", "mlh:uni", "taikai:us"]
          and "students only" in saved["checked"]["mlh:uni"]["reasons"][0],
          f"rejections are remembered with their reasons: {saved['checked']}")

    # ── 3. Nothing new: no email, no page re-read, no change to the state file ─
    before = open(state).read()
    rc = run(world, state)
    cases += 3
    check(failures, rc == 0 and not world.sent, f"an unchanged listing sends nothing: {world.sent}")
    check(failures, not world.fetched, f"rejected pages are not re-read within a week: {world.fetched}")
    check(failures, open(state).read() == before, "an unchanged listing must not rewrite the state file")

    # ...a week later the rejected pages are read again (rules change).
    run(world, state, now=NOW + timedelta(days=hw.RECHECK_AFTER_DAYS + 1))
    cases += 1
    check(failures, sorted(world.fetched) == ["devfolio:campus", "mlh:uni", "taikai:us"],
          f"rejected pages are re-read after a week: {world.fetched}")

    # ── 4. A new hackathon is announced: one alert, then never again ─────────
    world.events.append(ev("Devpost", "paypal", "PayPal AI Hackathon", 40, prize="$70,000"))
    world.pages["devpost:paypal"] = ("Join hackathon Who can participate Above legal age of majority in country "
                                     "of residence All countries/territories View full rules $67,500 in cash. "
                                     "Registration Period: October 1, 2026 - November 5, 2026 Submission Period")
    rc = run(world, state)
    cases += 3
    check(failures, rc == 0 and len(world.sent) == 1, f"one alert for one new hackathon: {world.sent}")
    subject = world.sent[0]["subject"] if world.sent else ""
    check(failures, subject == "AI hackathon, $67,500 cash: PayPal AI Hackathon", f"alert subject: {subject!r}")
    check(failures, world.sent and world.sent[0]["to"] == "rahul@example.com"
          and "Sign up by Thu 05 Nov 2026" in world.sent[0]["text"]
          and "Who can enter: Above legal age" in world.sent[0]["text"]
          and "https://paypal.example.com/" in world.sent[0]["html"],
          f"alert body: {world.sent and world.sent[0]['text']!r}")
    run(world, state)
    cases += 1
    check(failures, not world.sent, f"the same hackathon must not be mailed twice: {world.sent}")

    # ── 5. The same hackathon on a second platform is not new ────────────────
    world.events.append(ev("mlcontests", "paypal2", "PayPal AI Hackathon", 40))
    run(world, state)
    cases += 1
    check(failures, not world.sent, f"a hackathon already mailed from Devpost was mailed again: {world.sent}")

    # ...but the same name a month apart is another organiser's event.
    world.events.append(ev("Zindi", "paypal3", "PayPal AI Hackathon", 75))
    run(world, state)
    cases += 1
    check(failures, len(world.sent) == 1 and "PayPal" in world.sent[0]["subject"],
          f"one name with a deadline a month apart is a new event: {[m['subject'] for m in world.sent]}")

    # ── 6. Several at once: one email, biggest cash first ────────────────────
    world.events += [ev("MLH", "vibe", "VibeCode AI Arena", 12, kind="end", prize="$6,000"),
                     ev("AIcrowd", "big", "Big Model AI Challenge", 28, kind="end", prize="$150,000+ Prize Money"),
                     ev("Devfolio", "late", "Too Late AI Sprint", 3)]
    run(world, state)
    cases += 2
    check(failures, len(world.sent) == 1
          and world.sent[0]["subject"] == "2 AI hackathons you can enter, up to $150,000 cash",
          f"two new hackathons, one email: {[m['subject'] for m in world.sent]}")
    check(failures, world.sent and "Ends Thu 15 Oct 2026 (12 days to build)" in world.sent[0]["text"]
          and world.sent[0]["text"].index("Big Model") < world.sent[0]["text"].index("VibeCode"),
          f"multi alert body: {world.sent and world.sent[0]['text']!r}")

    # ── 7. A failed send records nothing, so the next run retries ────────────
    world.events.append(ev("Hackster", "infineon", "Infineon Boss Battle in the AI Arena", 93, prize="$20,000"))
    world.fail_send = True
    rc = run(world, state)
    cases += 2
    check(failures, rc == 1, f"a failed send must exit 1, got {rc}")
    check(failures, "hackster:infineon" not in json.load(open(state))["seen"],
          "an event whose email failed must not be recorded")
    world.fail_send = False
    run(world, state)
    cases += 1
    check(failures, len(world.sent) == 1 and "Infineon" in world.sent[0]["subject"],
          f"the next run must retry the failed alert: {[m['subject'] for m in world.sent]}")

    # ── 8. A page that cannot be read is not mailed, and is tried again ──────
    world.events.append(ev("Devpost", "flaky", "Flaky Page AI Hack", 30, prize="$30,000"))
    world.pages["devpost:flaky"] = ConnectionError("Connection reset by peer")
    run(world, state)
    cases += 2
    check(failures, not world.sent, f"an unreadable page must not be mailed: {world.sent}")
    check(failures, "devpost:flaky" not in json.load(open(state))["checked"],
          "an unreadable page must not be remembered as rejected")
    world.pages["devpost:flaky"] = OPEN_PAGE + " $30,000 in cash."
    run(world, state)
    cases += 1
    check(failures, len(world.sent) == 1 and "Flaky Page" in world.sent[0]["subject"],
          f"the page is read again next run: {[m['subject'] for m in world.sent]}")

    # ── 9. Pages read per run are capped, biggest listed prize first ─────────
    many = [ev("Devpost", f"bulk{i}", f"Bulk AI Hackathon Number {i}", 30, prize=f"${10_000 + i * 1000:,}")
            for i in range(hw.MAX_CHECKS_PER_RUN + 5)]
    world4 = World(list(many))
    capped = os.path.join(tmp, "capped.json")
    run(world4, capped)
    cases += 3
    check(failures, len(world4.fetched) == hw.MAX_CHECKS_PER_RUN, f"pages read: {len(world4.fetched)}")
    check(failures, "devpost:bulk0" not in world4.fetched and f"devpost:bulk{hw.MAX_CHECKS_PER_RUN + 4}"
          in world4.fetched, "the biggest listed prizes are read first")
    run(world4, capped)
    check(failures, sorted(world4.fetched) == [f"devpost:bulk{i}" for i in range(5)],
          f"the rest are read next run: {sorted(world4.fetched)}")

    # ── 10. Every platform failing exits 1 and records nothing ───────────────
    world3 = World(list(base), errors={p: "ConnectionError" for p in ALL})
    empty = os.path.join(tmp, "empty.json")
    cases += 2
    check(failures, run(world3, empty) == 1, "every platform failing must exit 1")
    check(failures, not os.path.exists(empty), "nothing is written when nothing was read")

    # ── 11. A platform down for a day gets one email, and one when it is back ─
    world.errors = {"TAIKAI": "HTTPError: 403 Forbidden"}
    run(world, state, now=NOW)
    cases += 1
    check(failures, not world.sent, f"a platform down for an hour sends nothing: {world.sent}")
    run(world, state, now=NOW + timedelta(hours=25))
    cases += 2
    check(failures, len(world.sent) == 1 and world.sent[0]["subject"] == "Hackathon alerts: TAIKAI unreadable",
          f"a day down sends one warning: {[m['subject'] for m in world.sent]}")
    check(failures, world.sent and "403" in world.sent[0]["text"], "the warning names the error")
    run(world, state, now=NOW + timedelta(hours=26))
    cases += 1
    check(failures, not world.sent, f"the warning is sent once: {[m['subject'] for m in world.sent]}")
    world.errors = {}
    run(world, state, now=NOW + timedelta(hours=27))
    cases += 2
    check(failures, len(world.sent) == 1 and world.sent[0]["subject"] == "Hackathon alerts: TAIKAI back",
          f"recovery sends one note: {[m['subject'] for m in world.sent]}")
    check(failures, "TAIKAI" not in json.load(open(state))["failing"], "recovery clears the failing entry")

    # ── 12. Old entries are forgotten a month on ─────────────────────────────
    st = hw.empty_state()
    st["seen"] = {"a": {"name": "Old", "deadline": "2026-08-01"}, "b": {"name": "Recent", "deadline": "2026-09-20"},
                  "c": {"name": "No date", "deadline": None}}
    st["checked"] = {"x": {"name": "Old reject", "date": "2026-08-01"}, "y": {"name": "New", "date": "2026-10-01"}}
    hw.forget_expired(st, TODAY)
    cases += 1
    check(failures, sorted(st["seen"]) == ["b", "c"] and sorted(st["checked"]) == ["y"],
          f"forget_expired kept {sorted(st['seen'])} and {sorted(st['checked'])}")

    # ── 13. HackerEarth refuses GitHub's servers, so it is not watched ───────
    world.events.append(ev("HackerEarth", "he", "HackerEarth GenAI Sprint", 30))
    run(world, state)
    cases += 2
    check(failures, "HackerEarth" not in ALL, "HackerEarth must not be in the watched platforms")
    check(failures, not world.sent, f"an event on an unwatched platform was mailed: {world.sent}")

    # ── 14. Unknown deadlines are mailed, marked ─────────────────────────────
    world.events.append(ev("TAIKAI", "lab", "SpaceXAI Digital Transformation Lab", None, kind="end"))
    run(world, state)
    cases += 1
    check(failures, world.sent and "Submission deadline not listed, check the page" in world.sent[0]["text"],
          f"an event with no deadline is mailed and marked: {world.sent and world.sent[0]['text']!r}")

    # ── 15. A state file from before the checks is replaced: everything that passes is mailed
    old = os.path.join(tmp, "v1.json")
    with open(old, "w") as f:
        json.dump({"version": 1, "platforms": {p: "2026-10-03" for p in ALL},
                   "seen": {"mlcontests:arc": {"name": "ARC Prize 2026 - ARC-AGI-3", "deadline": "2026-11-02"}},
                   "failing": {}}, f)
    world5 = World(list(base), pages=dict(pages))
    run(world5, old)
    cases += 2
    check(failures, len(world5.sent) == 1 and world5.sent[0]["subject"].endswith(": 4 open"),
          f"an old state file sends the full checked list once: {[m['subject'] for m in world5.sent]}")
    check(failures, json.load(open(old))["version"] == hw.STATE_VERSION, "the old state file is replaced")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
