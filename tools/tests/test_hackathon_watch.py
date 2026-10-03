"""Cases for hackathon_watch.py, the hourly new-hackathon email.

The watcher's job is narrow and easy to get wrong in both directions: miss a
new hackathon, or mail rahul the same one twice (or all seventy open ones on the
first run, or whenever a platform comes back). Each case below drives run() with
a fake platform reader and a fake mailbox, so nothing touches the network.

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
ALL = [name for name, _ in hs.PLATFORMS]


def check(failures, cond, msg):
    if not cond:
        failures.append(msg)


def ev(platform, key, name, days, ai=True, restricted="", kind="submission"):
    deadline = TODAY + timedelta(days=days) if days is not None else None
    return hs.event(platform, f"{platform.lower()}:{key}", name, f"https://{key}.example.com/", deadline,
                    kind, prize="$10,000", where="Online", ai=ai, restricted=restricted)


class World:
    """The platforms' listings and the mailbox, as one run sees them."""

    def __init__(self, events, errors=None):
        self.events, self.errors, self.sent, self.fail_send = events, errors or {}, [], False

    def collect(self, today):
        return [e for e in self.events if e["platform"] not in self.errors], dict(self.errors)

    def send(self, to, subject, text, body):
        if self.fail_send:
            raise RuntimeError("HTTP 403")
        self.sent.append({"to": to, "subject": subject, "text": text, "html": body})


def run(world, state, now=NOW, dry_run=False):
    """One watcher run, its progress lines swallowed so a failure's FAIL lines
    are what verify_edition.py shows."""
    world.sent = []
    with contextlib.redirect_stdout(io.StringIO()):
        return hw.run(state, to="rahul@example.com", dry_run=dry_run, now=now,
                      collect=world.collect, send=world.send)


def main():
    failures, cases = [], 0
    tmp = tempfile.mkdtemp()
    state = os.path.join(tmp, "seen.json")

    base = [
        ev("Devpost", "qloo", "Qloo Agentic Hackathon", 27),
        ev("lablab.ai", "amd", "AMD Developer Hackathon ACT III", 15, kind="end"),
        ev("mlcontests", "arc", "ARC Prize 2026 - ARC-AGI-3", 30),
        ev("Devpost", "soon", "Closing Soon AI Hack", 6),               # under 7 days: never mailed
        ev("Devpost", "nonai", "Climate Data Jam", 20, ai=False),       # not AI: never mailed
        ev("Devpost", "invite", "Invite Only AI Hack", 20, restricted="invite-only"),
    ]
    world = World(list(base))

    # ── 1. A dry run prints, sends nothing and writes nothing ────────────────
    cases += 2
    check(failures, run(world, state, dry_run=True) == 0, "dry run must exit 0")
    check(failures, not world.sent and not os.path.exists(state),
          "a dry run must not send mail or write the state file")

    # ── 2. First run: one welcome email with what is open, nothing else ──────
    rc = run(world, state)
    cases += 5
    check(failures, rc == 0, f"first run exit code {rc}")
    check(failures, len(world.sent) == 1 and world.sent[0]["subject"].startswith("Hackathon alerts are on: 3 "),
          f"first run sends one welcome email naming 3 hackathons: {[m['subject'] for m in world.sent]}")
    text = world.sent[0]["text"] if world.sent else ""
    check(failures, "Closing Soon" not in text and "Climate Data" not in text and "Invite Only" not in text,
          f"the welcome email lists only AI hackathons anyone can enter with 7+ days:\n{text}")
    check(failures, text.index("AMD") < text.index("Qloo") < text.index("ARC"),
          "the welcome email lists the soonest deadline first")
    saved = json.load(open(state))
    check(failures, sorted(saved["platforms"]) == sorted(ALL) and len(saved["seen"]) == 3,
          f"state after the first run: platforms={sorted(saved['platforms'])} seen={sorted(saved['seen'])}")

    # ── 3. Nothing new: no email, no change to the state file ────────────────
    before = open(state).read()
    rc = run(world, state)
    cases += 2
    check(failures, rc == 0 and not world.sent, f"an unchanged listing sends nothing: {world.sent}")
    check(failures, open(state).read() == before, "an unchanged listing must not rewrite the state file")

    # ── 4. A new hackathon is announced: one alert, then never again ─────────
    world.events.append(ev("Devpost", "paypal", "PayPal AI Hackathon", 40))
    rc = run(world, state)
    cases += 3
    check(failures, rc == 0 and len(world.sent) == 1, f"one alert for one new hackathon: {world.sent}")
    subject = world.sent[0]["subject"] if world.sent else ""
    check(failures, subject == "New AI hackathon: PayPal AI Hackathon (closes 12 Nov)",
          f"alert subject: {subject!r}")
    check(failures, world.sent and world.sent[0]["to"] == "rahul@example.com"
          and "40 days to build" in world.sent[0]["text"]
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
    world.events.append(ev("Unstop", "paypal3", "PayPal AI Hackathon", 75))
    run(world, state)
    cases += 1
    check(failures, len(world.sent) == 1 and "PayPal" in world.sent[0]["subject"],
          f"one name with a deadline a month apart is a new event: {[m['subject'] for m in world.sent]}")

    # ── 6. Several at once: one email, soonest first ─────────────────────────
    world.events += [ev("HackerEarth", "vibe", "VibeCode AI Arena", 12, kind="end"),
                     ev("Devfolio", "tum", "TUM Blockchain & AI Hackathon", 28, kind="end"),
                     ev("Unstop", "late", "Too Late AI Sprint", 3)]
    run(world, state)
    cases += 2
    check(failures, len(world.sent) == 1 and world.sent[0]["subject"] == "2 new AI hackathons on Devfolio, HackerEarth",
          f"two new hackathons, one email: {[m['subject'] for m in world.sent]}")
    check(failures, world.sent and "Ends Thu 15 Oct 2026 (12 days to build)" in world.sent[0]["text"]
          and world.sent[0]["text"].index("VibeCode") < world.sent[0]["text"].index("TUM"),
          f"multi alert body: {world.sent and world.sent[0]['text']!r}")

    # ── 7. A failed send records nothing, so the next run retries ────────────
    world.events.append(ev("Hackster", "infineon", "Infineon Boss Battle in the AI Arena", 93))
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

    # ── 8. A platform read for the first time is recorded quietly ────────────
    fresh = os.path.join(tmp, "partial.json")
    world2 = World(list(base), errors={"mlcontests": "HTTPError: 503"})
    run(world2, fresh)
    cases += 1
    check(failures, "mlcontests" not in json.load(open(fresh))["platforms"],
          "a platform that failed must not count as read")
    world2.errors = {}
    world2.events.append(ev("mlcontests", "gemma", "Build Coding Agents with Gemma 4", 60))
    run(world2, fresh)
    cases += 2
    check(failures, not world2.sent, f"a platform's first successful read must not mail its listing: "
                                     f"{[m['subject'] for m in world2.sent]}")
    check(failures, "mlcontests:gemma" in json.load(open(fresh))["seen"],
          "a platform's first listing must be recorded as seen")

    # ── 9. Every platform failing exits 1 and records nothing ────────────────
    world3 = World(list(base), errors={p: "ConnectionError" for p in ALL})
    empty = os.path.join(tmp, "empty.json")
    cases += 2
    check(failures, run(world3, empty) == 1, "every platform failing must exit 1")
    check(failures, not os.path.exists(empty), "nothing is written when nothing was read")

    # ── 10. A platform down for a day gets one email, and one when it is back ─
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

    # ── 11. Seen events are forgotten a month after their deadline ───────────
    st = hw.empty_state()
    st["seen"] = {"a": {"name": "Old", "deadline": "2026-08-01"}, "b": {"name": "Recent", "deadline": "2026-09-20"},
                  "c": {"name": "No date", "deadline": None}}
    hw.forget_expired(st, TODAY)
    cases += 1
    check(failures, sorted(st["seen"]) == ["b", "c"], f"forget_expired kept {sorted(st['seen'])}")

    # ── 12. Unknown deadlines are mailed, marked ─────────────────────────────
    world.events.append(ev("TAIKAI", "lab", "SpaceXAI Digital Transformation Lab", None, kind="end"))
    run(world, state)
    cases += 1
    check(failures, world.sent and "Deadline not listed, check the page" in world.sent[0]["text"],
          f"an event with no deadline is mailed and marked: {world.sent and world.sent[0]['text']!r}")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
