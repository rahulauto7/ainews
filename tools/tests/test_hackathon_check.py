"""Cases for hackathon_check.py, the page check before a hackathon alert.

rahul, 2026-10-12: only online AI hackathons with more than $5,000 in cash,
whose sign-up is still open and whose rules let rahul enter: an Indian citizen in
India, working at state-owned IOCL. Each case below is page text written the
way the real pages put it (Devpost's "Who can participate" box, Kaggle's rules,
Zindi's and lablab's descriptions), so nothing touches the network.

Run: python3 tools/tests/test_hackathon_check.py
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hackathon_check as hc
import hackathon_sources as hs

TODAY = date(2026, 10, 12)


def check(failures, cond, msg):
    if not cond:
        failures.append(msg)


def ev(platform="lablab.ai", prize="$10,000", online=True, reg_closes=None, url="https://x.example/"):
    e = hs.event(platform, f"{platform.lower()}:x", "Test AI Hackathon", url, date(2026, 11, 1), "end",
                 prize=prize, online=online, reg_closes=reg_closes)
    return e


DEVPOST_OK = ("Join hackathon Who can participate Above legal age of majority in country of residence "
              "All countries/territories, excluding standard exceptions View full rules "
              "$67,500 in cash 4 prizes. Registration Period: September 29, 2026 (10:00 am UTC) - "
              "November 10, 2026 (5:00 pm UTC) Submission Period: September 29, 2026 - November 12, 2026")
DEVPOST_STUDENTS = ("Join hackathon Who can participate Ages 18+ only All countries/territories Students only "
                    "View full rules $10,000 in cash. Open to all builders.")
DEVPOST_COUNTRIES = ("Join hackathon Who can participate Above legal age of majority Specific "
                     "countries/territories included United States Canada View full rules $25,000 in cash")
DEVPOST_INDIA_OUT = ("Join hackathon Who can participate Above legal age of majority All countries/territories "
                     "excluding Brazil, India, Quebec View full rules $25,000 in cash")
DEVPOST_SWAG = "Join hackathon Who can participate Ages 18+ $50,000 in prizes: AWS credits, swag and gift cards."
KAGGLE = ("Online competition on Kaggle. Total prizes: 65,000 USD. Entry deadline: 2026-11-25.\n"
          "ELIGIBILITY To be eligible to enter the Competition, you must be: not a resident of Crimea, Cuba, "
          "Iran, or North Korea; and Competitions are open to residents of the United States and worldwide, "
          "except that if you are a resident of Crimea, Cuba, Iran, North Korea, you are not eligible. "
          "Employees, interns, contractors, officers and directors of Competition Entities may enter and "
          "participate in the Competition, but are not eligible to win any Prizes.")


def main():
    failures, cases = [], 0

    def expect(name, e, text, ok, reason=""):
        nonlocal cases
        cases += 1
        got = hc.check(e, text, TODAY)
        check(failures, got["ok"] is ok and (not reason or any(reason in r for r in got["reasons"])),
              f"{name}: ok={got['ok']} reasons={got['reasons']}, want ok={ok}" + (f" with {reason!r}" if reason else ""))
        return got

    # ── Who can enter ────────────────────────────────────────────────────────
    got = expect("Devpost open to all countries", ev("Devpost", prize="$70,000 in prizes"), DEVPOST_OK, True)
    cases += 2
    check(failures, got["cash_usd"] == 67_500, f"Devpost cash is the 'in cash' figure: {got['cash_usd']}")
    check(failures, got["reg_closes"] == date(2026, 11, 10), f"Devpost registration period end: {got['reg_closes']}")
    expect("Devpost Students-only tag outranks 'open to all'", ev("Devpost"), DEVPOST_STUDENTS, False, "students only")
    expect("Devpost limited to some countries", ev("Devpost"), DEVPOST_COUNTRIES, False, "not India")
    expect("Devpost excluding India", ev("Devpost"), DEVPOST_INDIA_OUT, False, "India excluded")
    got = expect("Kaggle worldwide rules", ev("mlcontests", prize="$65,000"), KAGGLE, True)
    cases += 2
    check(failures, got["reg_closes"] == date(2026, 11, 25), f"Kaggle entry deadline: {got['reg_closes']}")
    check(failures, "worldwide" in got["who"], f"Kaggle who line: {got['who']!r}")
    expect("students only", ev(), "This hackathon is open only to currently enrolled university students. Online.",
           False, "students only")
    expect("students and professionals", ev(),
           "Open to students and working professionals from any country. Online event.", True)
    expect("a student-only award is not a student-only event", ev(),
           "Open to everyone. Rising Star Award (Student Only): $1,000. Online.", True)
    expect("residents of one country", ev(), "Online. The contest is open only to legal residents of the "
           "United States who are 18 or older.", False, "other countries")
    expect("residents including India", ev(), "Online. Open to legal residents of India, Kenya and Nigeria.", True)
    expect("live in a list of countries", ev(), "Online. This competition is open ONLY to participants who live "
           "in the following countries: Jamaica, Barbados, Trinidad.", False, "other countries")
    expect("India excluded in prose", ev(), "Online. Residents of India and Pakistan are not eligible.",
           False, "India excluded")
    expect("Indiana is not India", ev(), "Online. Residents of Indiana are not eligible for the travel grant.", True)
    got = expect("government staff excluded: enter as a founder", ev(), "Online. Employees of any government "
                 "or state-owned enterprise are not eligible to participate.", True)
    cases += 1
    check(failures, got["notes"] and "founder" in got["notes"][0], f"founder note: {got['notes']}")
    expect("one company's staff", ev(), "Online. This challenge is open only to employees of Acme Corp.",
           False, "staff or members")
    expect("Devpost menu is not a staff-only rule", ev("Devpost"),
           "Host an internal hackathon " + DEVPOST_OK, True)

    # ── Cash ─────────────────────────────────────────────────────────────────
    expect("small prize", ev(prize="$2,000"), "Online. Open to all.", False, "under $5,000")
    expect("no prize", ev(prize=""), "Online. Open to all. Win swag and certificates.", False, "none found")
    expect("Devpost prizes with no cash", ev("Devpost", prize="$50,000"), DEVPOST_SWAG + " Online.", False,
           "under $5,000")
    expect("rupee prize converted", ev(prize="₹1,00,000"), "Online. Open to all.", False, "under $5,000")
    got = expect("prize read from the page", ev(prize=""), "Online. Open to all. Total prize pool: $25,000 in cash.",
                 True)
    cases += 1
    check(failures, got["cash_usd"] == 25_000, f"page prize: {got['cash_usd']}")

    # ── Online ───────────────────────────────────────────────────────────────
    expect("listed in person", ev(online=False), "Open to all.", False, "in person")
    expect("unknown, venue and no online option", ev(online=None),
           "Open to all. Venue: Lisbon Congress Centre. In-person event.", False, "in person")
    expect("unknown, nothing said", ev(online=None), "Maratona de inovação. Open to all.", False,
           "no paid travel")

    # ── In person or hybrid: only with the trip paid (rahul, 2026-10-12) ─────
    got = expect("in person with flights covered", ev(online=False),
                 "Held in Singapore. Open to all. Flights and accommodation are covered for all finalists. "
                 "We provide visa invitation letters.", True)
    cases += 2
    check(failures, got["in_person"] and "Flights and accommodation are covered" in got["travel"],
          f"travel evidence: {got['travel']!r}")
    check(failures, "invitation letters" in got["visa"], f"visa evidence: {got['visa']!r}")
    expect("hybrid with travel grants", ev(online=None), "A hybrid hackathon in Berlin with a venue on site. "
           "Open to all. Travel grants available for international teams.", True)
    expect("in person, travel at own expense", ev(online=False), "Held in London. Open to all. "
           "Participants are responsible for travel costs and travel is not covered.", False, "no paid travel")
    expect("in person, nothing about travel", ev(online=False), "Held in Bengaluru. Open to all. Free food.",
           False, "no paid travel")
    got = expect("online needs no travel", ev(), "Online. Open to all.", True)
    cases += 1
    check(failures, not got["in_person"] and not got["travel"], f"online event: {got}")
    expect("unknown, page says virtual", ev(online=None), "A fully virtual hackathon. Open to all.", True)

    # ── Sign-up ──────────────────────────────────────────────────────────────
    expect("listing's sign-up closed", ev(reg_closes=date(2026, 10, 5)), "Online. Open to all.", False,
           "registration closed")
    expect("page says registration closed", ev(), "Online. Open to all. Registrations are now closed.", False,
           "registration closed")
    got = expect("listing's sign-up still open", ev(reg_closes=date(2026, 10, 30)), "Online. Open to all.", True)
    cases += 1
    check(failures, got["reg_closes"] == date(2026, 10, 30), f"sign-up date carried: {got['reg_closes']}")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
