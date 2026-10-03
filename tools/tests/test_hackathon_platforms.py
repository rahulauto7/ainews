"""Cases for the hackathon platforms in hackathon_sources.py.

Every reader is fed a fixture built the way the real page or JSON was on 2-3 Oct
2026, trimmed to the fields the reader uses, so a platform changing shape shows
up here rather than as an empty block in .tmp/hackathons.txt.

lablab.ai has no API and no feed; its events sit in the page's Next.js data
chunks (self.__next_f.push). The fixture below is built the way the page is:
the records' text is JSON-escaped into one push call, with each record's keys in
the order seen on the real page.

Run: python3 tools/tests/test_hackathon_platforms.py
"""

import html as html_lib
import json
import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import find_opportunities
import hackathon_sources as hs

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
TODAY = date(2026, 10, 3)


def check(failures, cond, msg):
    if not cond:
        failures.append(msg)


def record(name, slug, start, end, kind="HACKATHON", signup=True):
    return (f'{{"id":"kf{slug[:6]}x","name":"{name}","orderIndex":null,"description":"x",'
            f'"signupActive":{str(signup).lower()},'
            f'"oneCouponPerParticipant":false,"endAt":"{end}","startAt":"{start}",'
            f'"toBeAnnounced":false,"image":"/x.png","slug":"{slug}","previousSlugs":[],'
            f'"teamsActive":true,"type":"{kind}"}}')


def page(*records):
    payload = '1:["$","div",null,{"events":[' + ",".join(records) + "]}]"
    chunk = json.dumps(payload)[1:-1]
    return f'<html><script>self.__next_f.push([1,"{chunk}"])</script></html>'


def main():
    failures, cases = [], 0
    parse = getattr(find_opportunities, "parse_lablab_listing", None)
    if not parse:
        print("FAIL: find_opportunities.parse_lablab_listing does not exist")
        print("1 failure(s) of 1")
        return 1

    # ── 1. An ended event is dropped, an open one returned whole ─────────────
    html = page(
        record("Old Hack", "old-hack-2025", "2025-03-01T19:00:00.000Z", "2025-03-08T19:00:00.000Z"),
        record("AMD Developer Hackathon ACT III", "amd-developer-hackathon-act-iii",
               "2026-10-12T19:00:00.000Z", "2026-10-18T19:00:00.000Z"),
    )
    got = parse(html, NOW)
    cases += 2
    check(failures, len(got) == 1, f"only the open event: {got!r}")
    check(failures, got and got[0] == {"slug": "amd-developer-hackathon-act-iii",
                                       "name": "AMD Developer Hackathon ACT III", "start": "2026-10-12",
                                       "end": "2026-10-18", "end_at": "2026-10-18T19:00:00.000Z",
                                       "signup": True},
          f"open event record: {got and got[0]!r}")

    # ── 2. No data chunks: nothing, and no exception ─────────────────────────
    cases += 1
    try:
        check(failures, parse("<html><body>Maintenance</body></html>", NOW) == [],
              "a page with no __next_f chunks must return []")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"a page with no __next_f chunks raised {exc!r}")

    # ── 3. Workshops are not hackathons ──────────────────────────────────────
    html = page(record("Agents Workshop", "agents-workshop", "2026-10-05T19:00:00.000Z",
                       "2026-10-06T19:00:00.000Z", kind="WORKSHOP"))
    cases += 1
    check(failures, parse(html, NOW) == [], "a WORKSHOP must be left out")

    # ── Soonest deadline first ───────────────────────────────────────────────
    html = page(
        record("Later", "later", "2026-11-01T19:00:00.000Z", "2026-11-08T19:00:00.000Z"),
        record("Sooner", "sooner", "2026-10-01T19:00:00.000Z", "2026-10-06T19:00:00.000Z", signup=False),
    )
    got = parse(html, NOW)
    cases += 2
    check(failures, [e["slug"] for e in got] == ["sooner", "later"], f"order: {got!r}")
    check(failures, got and got[0]["signup"] is False, "signupActive false must read as False")

    # ── lablab events: the end is the deadline, a closed sign-up is flagged ──
    evs = hs.lablab_events(got)
    cases += 2
    check(failures, evs[0]["deadline"] == date(2026, 10, 7) and evs[0]["deadline_kind"] == "end",
          f"lablab deadline is the end in IST: {evs[0]!r}")
    check(failures, evs[0]["restricted"] == "sign-up closed" and not evs[1]["restricted"],
          f"lablab sign-up flag: {[e['restricted'] for e in evs]!r}")

    # ── Devpost: the submission period's end, invite-only, a $0 prize ────────
    cases += 4
    for period, want in (("Oct 02 - 04, 2026", date(2026, 10, 4)),
                         ("Sep 01 - Oct 23, 2026", date(2026, 10, 23)),
                         ("Dec 15, 2025 - Jan 05, 2026", date(2026, 1, 5)),
                         ("Oct 23, 2026", date(2026, 10, 23))):
        check(failures, hs.devpost_deadline(period) == want,
              f"devpost_deadline({period!r}) = {hs.devpost_deadline(period)!r}, want {want}")
    row = {"id": 31598, "title": "CodeML", "url": "https://codeml-31598.devpost.com/",
           "submission_period_dates": "Oct 02 - 04, 2026", "prize_amount": "$<span>0</span>",
           "prizes_counts": {"cash": 0}, "themes": [{"name": "Machine Learning/AI"}],
           "invite_only": True, "displayed_location": {"location": "Online"}}
    e = hs.devpost_event(row)
    cases += 4
    check(failures, e["key"] == "devpost:31598", f"devpost key: {e['key']!r}")
    check(failures, e["ai"], "the Machine Learning/AI theme makes a Devpost event AI")
    check(failures, e["restricted"] == "invite-only", f"invite-only: {e['restricted']!r}")
    check(failures, e["prize"] == "", f"a $0 prize prints nothing, got {e['prize']!r}")
    row.update(prize_amount="$<span data-currency-value>138,000</span>", prizes_counts={"cash": 12},
               themes=[], title="Build, Ship, Shape: Amazon Developer Hackathon")
    e = hs.devpost_event(row)
    cases += 2
    check(failures, e["prize"] == "$138,000 (12 cash prizes)", f"devpost prize: {e['prize']!r}")
    check(failures, not e["ai"], "no AI theme and no AI word in the title: not AI")

    # ── mlcontests: deadline, not registration deadline; past ones dropped ───
    comps = [
        {"name": "ARC Prize 2026 - ARC-AGI-3", "url": "https://www.kaggle.com/competitions/arc?ref=mlcontests",
         "deadline": "2 Nov 2026", "registration-deadline": "26 Oct 2026", "prize": "$850,000",
         "platform": "Kaggle"},
        {"name": "Old one", "url": "https://x.org/old", "deadline": "1 Aug 2026", "platform": "Codabench"},
        {"name": "Indie", "url": "https://indie.ai/c", "deadline": "15 Nov 2026", "platform": "Independent"},
    ]
    page_html = f'<div id="competitions" data-competitions="{html_lib.escape(json.dumps(comps), quote=True)}"></div>'
    got = hs.parse_mlcontests(page_html, TODAY)
    cases += 4
    check(failures, [e["name"] for e in got] == ["ARC Prize 2026 - ARC-AGI-3", "Indie"],
          f"mlcontests open events: {[e['name'] for e in got]!r}")
    check(failures, got and got[0]["deadline"] == date(2026, 11, 2),
          f"mlcontests must use the submission deadline, not registration: {got and got[0]['deadline']!r}")
    check(failures, got and got[0]["url"] == "https://www.kaggle.com/competitions/arc",
          f"the ?ref=mlcontests tag is dropped: {got and got[0]['url']!r}")
    check(failures, len(got) > 1 and got[1]["where"] == "", "'Independent' is not printed as a place")

    # ── HackerEarth: hackathons only, end in IST ─────────────────────────────
    data = {"response": [
        {"title": "VibeCode Arena: AI Innovation Arena", "description": "Build with AI",
         "url": "https://www.hackerearth.com/challenges/hackathon/vibecode-arena/",
         "end_utc_tz": "2026-10-20 18:29:00+00:00"},
        {"title": "HCLTech Java Engineering Hiring Challenge", "description": "AI and Java",
         "url": "https://www.hackerearth.com/challenges/competitive/hcltech-java/",
         "end_utc_tz": "2026-10-20 18:29:00+00:00"},
    ]}
    got = hs.parse_hackerearth(data, TODAY)
    cases += 2
    check(failures, [e["name"] for e in got] == ["VibeCode Arena: AI Innovation Arena"],
          f"HackerEarth hiring challenges are not hackathons: {got!r}")
    check(failures, got and got[0]["deadline"] == date(2026, 10, 20) and got[0]["ai"],
          f"HackerEarth 18:29 UTC is 23:59 IST the same day: {got and got[0]!r}")

    # ── Devfolio: ends_at, never reg_ends_at ─────────────────────────────────
    nd = {"props": {"pageProps": {"dehydratedState": {"queries": [{"state": {"data": {
        "open_hackathons": [
            {"slug": "tum", "name": "TUM Blockchain & AI Hackathon", "is_online": False,
             "ends_at": "2026-10-31T14:00:00+00:00", "themes": [{"theme": {"name": "No Restrictions"}}],
             "settings": {"reg_ends_at": "2026-10-04T12:00:00+00:00"}},
            {"slug": "hackverse", "name": "Hackverse.2026", "is_online": True,
             "ends_at": "2026-10-06T14:30:00+00:00", "themes": []}],
        "upcoming_hackathons": [
            {"slug": "tum", "name": "TUM Blockchain & AI Hackathon", "ends_at": "2026-10-31T14:00:00+00:00"}],
    }}}]}}}}
    page_html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(nd)}</script>'
    got = hs.parse_devfolio(page_html, TODAY)
    cases += 3
    check(failures, [e["key"] for e in got] == ["devfolio:tum", "devfolio:hackverse"],
          f"Devfolio events, de-duplicated across groups: {[e['key'] for e in got]!r}")
    check(failures, got and got[0]["deadline"] == date(2026, 10, 31),
          f"Devfolio uses ends_at, not the registration deadline: {got and got[0]['deadline']!r}")
    check(failures, [e["ai"] for e in got] == [True, False], f"Devfolio AI flags: {[e['ai'] for e in got]!r}")

    # ── Unstop: end_date, never the registration deadline ────────────────────
    data = {"data": {"data": [{
        "id": 1762328, "title": "Edge AI Challenge", "end_date": "2026-10-25T00:00:00+05:30",
        "regnRequirements": {"end_regn_dt": "2026-10-05T00:00:00+05:30"},
        "seo_url": "https://unstop.com/hackathons/edge-ai-challenge-1762328", "region": "online",
        "organisation": {"name": "IIT (ISM) Dhanbad"},
        "prizes": [{"cash": 10000, "currency": "fa-rupee"}, {"cash": 5000, "currency": "fa-rupee"}]}]}}
    got = hs.parse_unstop(data, TODAY)
    cases += 2
    check(failures, got and got[0]["deadline"] == date(2026, 10, 25),
          f"Unstop must not use the registration deadline: {got and got[0]['deadline']!r}")
    check(failures, got and got[0]["prize"] == "₹15,000 total cash", f"Unstop prize: {got and got[0]['prize']!r}")

    # ── MLH: ended events dropped, AI by name ────────────────────────────────
    props = {"props": {"upcomingEvents": [
        {"slug": "la-hacks-ai", "name": "LA Hacks AI Hackathon 2026", "status": "pending",
         "endsAt": "2026-10-18T20:00:00Z", "location": "Los Angeles, CA", "formatType": "physical",
         "websiteUrl": "https://ai.lahacks.com", "customFields": {"hackathon_focus": []}},
        {"slug": "mhacks", "name": "MHacks", "status": "pending", "endsAt": "2026-10-04T23:00:00Z",
         "formatType": "digital", "websiteUrl": "https://mhacks.org", "customFields": {}},
        {"slug": "old", "name": "Old AI Hacks", "status": "ended", "endsAt": "2026-10-04T23:00:00Z"}]}}
    page_html = f'<script data-page="app" type="application/json">{json.dumps(props)}</script>'
    got = hs.parse_mlh(page_html, TODAY)
    cases += 2
    check(failures, [e["key"] for e in got] == ["mlh:la-hacks-ai", "mlh:mhacks"], f"MLH events: {got!r}")
    check(failures, [e["ai"] for e in got] == [True, False] and got[1]["where"] == "Online",
          f"MLH AI flag and online format: {got!r}")

    # ── TAIKAI: open challenges, last step as the end ────────────────────────
    apollo = {
        "Challenge:1": {"name": "SpaceXAI Digital Transformation Lab", "isClosed": False, "slug": "lab",
                        "prize": 3500, "prizeCurrency": {"__ref": "PrizeCurrency:usd"},
                        "organization": {"__ref": "Organization:o"},
                        "steps": [{"__ref": "ChallengeStep:a"}, {"__ref": "ChallengeStep:b"}],
                        "industries": [{"__ref": "Industry:ai"}]},
        "Challenge:2": {"name": "Closed Hack", "isClosed": True, "slug": "closed",
                        "organization": {"__ref": "Organization:o"}, "steps": []},
        "PrizeCurrency:usd": {"name": "USD"}, "Organization:o": {"slug": "spacexai"},
        "ChallengeStep:a": {"startDate": "2026-09-15T23:00:00.000Z"},
        "ChallengeStep:b": {"startDate": "2026-10-27T16:00:00.000Z"},
        "Industry:ai": {"title": "Artificial Intelligence"},
    }
    page_html = (f'<script id="__NEXT_DATA__" type="application/json">'
                 f'{json.dumps({"props": {"apolloState": apollo}})}</script>')
    got = hs.parse_taikai(page_html, TODAY)
    cases += 2
    check(failures, len(got) == 1 and got[0]["url"] == "https://taikai.network/spacexai/hackathons/lab",
          f"TAIKAI open challenges: {got!r}")
    check(failures, got and got[0]["deadline"] == date(2026, 10, 27) and got[0]["prize"] == "3,500 USD"
          and got[0]["ai"], f"TAIKAI fields: {got and got[0]!r}")

    # ── Hackster: participation deadline; judging cards skipped ──────────────
    card = ('<a class="x" href="/contests/{slug}"><h4 class="h4">{title}</h4></a><div class="s">'
            '<span>With </span></div><div><p class="m">Participation open until:</p>'
            '<p class="b">{when}</p></div>')
    page_html = ('<a href="/contests/judging"><h4>Arduino UNO Q</h4></a><div>Judging in progress</div>'
                 + card.format(slug="infineon-boss-battle", title="Infineon Boss Battle in the AI Arena",
                               when="Jan 04, 2027")
                 + card.format(slug="sustain", title="Sustain the System", when="Apr 26, 2027"))
    got = hs.parse_hackster(page_html, TODAY)
    cases += 2
    check(failures, [e["key"] for e in got] == ["hackster:infineon-boss-battle", "hackster:sustain"],
          f"Hackster contests: {[e['key'] for e in got]!r}")
    check(failures, got and got[0]["deadline"] == date(2027, 1, 4) and got[0]["ai"] and not got[1]["ai"],
          f"Hackster fields: {got!r}")

    # ── What counts as AI ────────────────────────────────────────────────────
    for text, want in (("AI4Good Hackathon", True), ("Hack4AI", True), ("GenAI Sprint", True),
                       ("Agentic Systems Jam", True), ("TAMU Datathon", True), ("Dubai FinTech Hack", False),
                       ("HTML & CSS Jam", False), ("Gmail Add-on Contest", False)):
        cases += 1
        check(failures, hs.is_ai(text) is want, f"is_ai({text!r}) should be {want}")

    # ── collect(): one platform failing does not hide the others ─────────────
    def boom(today):
        raise RuntimeError("HTTP 403")
    events, errors = hs.collect(TODAY, platforms=(("Good", lambda t: [{"platform": "Good"}]), ("Bad", boom)))
    cases += 1
    check(failures, events == [{"platform": "Good"}] and list(errors) == ["Bad"] and "403" in errors["Bad"],
          f"collect: events={events!r} errors={errors!r}")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
