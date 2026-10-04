"""Cases for printing the AI Hackathons section biggest prize first.

rahul, 2026-10-03: "in PDF, give me hackathons with our top prizes first". The
PDF draws the section in prize order whatever order the builder wrote it in, so
a curator in a hurry cannot get it wrong, and the candidate lists the curator
picks from show the biggest prizes at the top of each platform. Prize lines come
in every shape the platforms and curators write ("$138k cash total ($25k 1st)",
"₹ 1,00,000", "20,000 EUR", "5,000 USDC"), and none is a number to sort on until
hackathon_sources.prize_usd reads it. All cases here are offline.

Run: python3 tools/tests/test_hackathon_prizes.py
"""

import contextlib
import io
import os
import re
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import find_opportunities
import hackathon_sources as hs
from generate_pdf import render_edition

SUMMARY = ("A global online hackathon for teams building AI agents. Entrants submit a working demo "
           "and a short video. The organiser pays cash prizes to the top three teams. Anyone over "
           "eighteen can enter from any country. Judging runs for two weeks after the deadline.")


def check(failures, cond, msg):
    if not cond:
        failures.append(msg)


def hackathon(title, prize=None):
    story = {"title": title, "summary": SUMMARY, "source": "Devpost", "relevance": 5,
             "url": f"https://{title.split()[0].lower()}.devpost.com/", "tags": ["hackathon"],
             "deadline": "30 Oct 2026"}
    if prize is not None:
        story["prize"] = prize
    return story


def main():
    failures, cases = [], 0

    # ── Reading a prize line as a rough dollar figure ────────────────────────
    for text, low, high in (
        ("$138k cash total ($25k 1st, Fire TV and Alexa+ tracks)", 138_000, 138_000),  # total, not 1st
        ("$67.5k cash total ($12k 1st)", 67_500, 67_500),
        ("$1,000,000 (19 cash prizes)", 1_000_000, 1_000_000),       # Devpost; 19 is a count
        ("$1.5M", 1_500_000, 1_500_000),
        ("$2 million pool", 2_000_000, 2_000_000),
        ("€10,680 (4 cash prizes)", 11_000, 12_500),
        ("10,000€", 10_000, 12_000),
        ("20,000 EUR", 20_000, 24_000),                               # TAIKAI
        ("3,500 USD", 3_500, 3_500),
        ("5,000 USDC", 5_000, 5_000),
        ("USD 50,000", 50_000, 50_000),
        ("USD50,000", 50_000, 50_000),
        ("£8k", 9_000, 12_000),
        ("₹ 100,000 (8 cash prizes)", 1_000, 1_400),                  # Devpost India
        ("₹1,00,000 cash", 1_000, 1_400),                             # Indian digit grouping
        ("₹15,000 total cash", 150, 200),                             # Unstop
        ("Rs. 2 lakh", 2_000, 2_800),
        ("INR 2 cr", 200_000, 280_000),
        ("$5k cash + $100k in AWS credits", 5_000, 5_000),            # credits are not cash
        ("$5k cash + $5k credits", 5_000, 5_000),
        ("$10,000, plus mentoring", 10_000, 10_000),
        ("Q4 2026 $500", 500, 500),                                   # a year is not money
        ("1st place 5,000", 0, 0),                                    # no currency
        ("Swag and cloud credits", 0, 0),
        ("rsvp by 5 Oct", 0, 0),
        ("", 0, 0),
        (None, 0, 0),
    ):
        cases += 1
        got = hs.prize_usd(text)
        check(failures, low <= got <= high, f"prize_usd({text!r}) = {got:,.2f}, want {low:,}-{high:,}")

    # ── Section order: biggest first, no prize last, ties keep the curator's ─
    stories = [hackathon("Small Hack", "$5k cash"), hackathon("Mystery Hack"),
               hackathon("Euro Hack", "20,000 EUR"), hackathon("Rupee Hack", "₹10 lakh"),
               hackathon("Huge Hack", "$138k cash total ($25k 1st)"),
               hackathon("Twin Hack A", "$5,000"), hackathon("Credit Hack", "$500k in API credits")]
    order = [s["title"] for s in hs.by_prize(stories)]
    want = ["Huge Hack", "Euro Hack", "Rupee Hack", "Small Hack", "Twin Hack A", "Mystery Hack", "Credit Hack"]
    cases += 2
    check(failures, order == want, f"by_prize order {order}, want {want}")
    check(failures, [s["title"] for s in stories][0] == "Small Hack", "by_prize must not reorder its input")

    # ── The PDF prints them in that order, whatever the builder wrote ────────
    data = {"sections": {"ai_hackathons": list(stories)}}
    from pypdf import PdfReader
    pdf = render_edition(data)
    text = " ".join(p.extract_text() for p in PdfReader(io.BytesIO(bytes(pdf.output()))).pages)
    text = re.sub(r"\s+", " ", text)
    found = {t: text.find(t) for t in want}
    cases += 3
    check(failures, all(i >= 0 for i in found.values()), f"titles missing from the PDF: {found}")
    check(failures, sorted(want, key=found.get) == want,
          f"PDF order {sorted(want, key=found.get)}, want {want}")
    check(failures, [s["title"] for s in data["sections"]["ai_hackathons"]][0] == "Small Hack",
          "render_edition must not reorder the edition it was given")

    # ── The candidate lists show the biggest prizes first ────────────────────
    today = hs.today_ist()
    events = [hs.event("TAIKAI", "taikai:a", "Agents Sprint", "https://a.example/", today + timedelta(days=10),
                       "end", prize="3,500 USD"),
              hs.event("TAIKAI", "taikai:b", "GenAI Grand Prix", "https://b.example/", today + timedelta(days=40),
                       "end", prize="20,000 EUR"),
              hs.event("TAIKAI", "taikai:c", "LLM Jam", "https://c.example/", today + timedelta(days=20), "end"),
              hs.event("TAIKAI", "taikai:d", "Vision AI Cup", "https://d.example/", today + timedelta(days=15),
                       "end"),
              hs.event("TAIKAI", "taikai:e", "Closing AI Hack", "https://e.example/", today + timedelta(days=3),
                       "end", prize="$90,000")]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        find_opportunities.platform_block("TAIKAI", lambda _today: events, {}, {})
    lines = [l for l in buf.getvalue().splitlines() if l.startswith("- ")]
    names = [next(e["name"] for e in events if e["name"] in l) for l in lines]
    cases += 1
    check(failures, names == ["GenAI Grand Prix", "Agents Sprint", "Vision AI Cup", "LLM Jam"],
          f"platform block order {names}: biggest prize first, then soonest deadline, "
          "and nothing closing in under 7 days")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
