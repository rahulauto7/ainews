"""Cases for find_roles.py, the careers section's open Forward Deployed and
Solutions Engineer roles.

rahul, 2026-10-03: the PDF should help toward "getting [a] remote AI job as forward
deployed eng or solution engineer in global companies, not [an] Indian company,
which work via remote and via visa". So a role is kept only in the FDE /
Solutions family, never an on-site or hybrid role in India, and the table ranks
remote roles open to India first, then roles whose posting says the company
sponsors visas.

Every reader is fed a fixture shaped like the board's real JSON on 3 Oct 2026,
trimmed to the fields the reader uses. All cases are offline.

Run: python3 tools/tests/test_find_roles.py
"""

import contextlib
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import builder_helpers
import find_roles as fr

TODAY = "2026-10-04"


def check(failures, cond, msg):
    if not cond:
        failures.append(msg)


def r(company="Acme AI", title="Forward Deployed Engineer", location="Remote", mode="remote",
      visa=None, posted="2026-10-02", url="https://example.com/job", source="ashby:acme",
      scope=None):
    return fr.role(company, title, location, mode, visa, posted, url, source) | {"visa_scope": scope}


class Resp:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def fake_get(routes):
    """A requests.get stand-in: the first route whose key is in the URL answers."""
    def get(url, **_):
        for key, data in routes.items():
            if key in url:
                if isinstance(data, Exception):
                    raise data
                return Resp(data)
        return Resp({"jobs": []})
    return get


def main():
    failures, cases = [], 0

    # ── 1. Visa wording ──────────────────────────────────────────────────────
    for text, want in [
        ("We sponsor visas for this role.", True),
        ("Visa sponsorship is available for exceptional candidates.", True),
        ("We offer relocation and visa support.", True),
        ("We are unable to sponsor visas at this time.", False),
        ("We do not offer visa sponsorship.", False),
        ("Candidates must be authorised to work; no visa support.", False),
        ("We do sponsor visas. We cannot sponsor contractors.", True),
        ("Great team, great benefits.", None),
        ("", None),
    ]:
        cases += 1
        check(failures, fr.visa_status(text) is want,
              f"visa_status({text!r}) is {fr.visa_status(text)}, expected {want}")
    cases += 2
    check(failures, fr.visa_scope("We can sponsor visas to Germany.") == "Germany",
          f"visa_scope missed Germany: {fr.visa_scope('We can sponsor visas to Germany.')!r}")
    check(failures, fr.visa_scope("We sponsor visas.") is None, "a plain sponsor line has no scope")

    # ── 2. What is kept ──────────────────────────────────────────────────────
    for case, want in [
        (r(), None),
        (r(title="Solutions Architect, Generative AI"), None),
        (r(title="Senior Sales Engineer"), None),
        (r(title="Account Executive"), "not an FDE or Solutions title"),
        (r(title="Manager, Forward Deployed Engineering"), "management or intern role"),
        (r(title="Solutions Engineer Intern"), "management or intern role"),
        (r(url=""), "no link"),
        (r(posted="2026-08-20"), "posted 45 days ago"),
        (r(location="Bengaluru, India", mode="onsite"), "on-site or hybrid in India"),
        (r(location="Gurugram", mode="hybrid"), "on-site or hybrid in India"),
        (r(location="Remote - India", mode="remote"), None),
        (r(location="London, UK", mode="onsite"), None),
    ]:
        cases += 1
        got = fr.keep(case, TODAY)
        check(failures, got == want,
              f"keep({case['title']!r}, {case['location']!r}, {case['mode']}) is {got!r}, "
              f"expected {want!r}")

    # ── 3. Tiers: remote and open to India, sponsors visas, remote elsewhere, rest ─
    for case, want, why in [
        (r(location="Remote"), 0, "remote with no region is worldwide"),
        (r(location="Remote (worldwide)"), 0, "remote worldwide"),
        (r(location="Remote (India, Singapore)"), 0, "remote open to India"),
        (r(location="Remote (APAC)"), 0, "remote open to Asia-Pacific"),
        (r(location="Remote (United States)"), 2, "remote limited to the US"),
        (r(title="Solutions Engineer, EMEA", location="Remote"), 2,
         "a region in the title overrides an empty location"),
        (r(location="London, UK", mode="onsite", visa=True), 1, "on-site abroad, sponsors visas"),
        (r(location="San Francisco, CA", mode="onsite", visa=True, scope="Germany"), 3,
         "sponsors visas only to Germany, the job is in the US"),
        (r(location="Berlin, Germany", mode="onsite", visa=True, scope="Germany"), 1,
         "sponsors visas to Germany, the job is in Germany"),
        (r(location="New York", mode="onsite", visa=None), 3, "visa not stated"),
        (r(location="New York", mode="onsite", visa=False), 3, "no visa sponsorship"),
    ]:
        cases += 1
        check(failures, fr.tier(case) == want, f"tier {fr.tier(case)}, expected {want}: {why}")

    # ── 4. Rank: by tier, then newest; duplicates collapse ───────────────────
    roles = [
        r(company="Old Remote", posted="2026-09-20"),
        r(company="Visa Co", location="London, UK", mode="onsite", visa=True, posted="2026-10-03"),
        r(company="New Remote", posted="2026-10-03"),
        r(company="New Remote", posted="2026-10-01"),  # same company, title, place
        r(company="India Office", location="Pune, India", mode="onsite", posted="2026-10-03"),
    ]
    ranked = fr.rank(roles, TODAY)
    cases += 2
    check(failures, [x["company"] for x in ranked] == ["New Remote", "Old Remote", "Visa Co"],
          f"rank order: {[x['company'] for x in ranked]}")
    check(failures, ranked[0]["posted"] == "2026-10-03", "a duplicate keeps the first seen")

    # ── 5. The table: both routes get seats, two roles a company at most ─────
    remote = [r(company=f"Remote {i}", posted=f"2026-10-{3 - i % 3:02d}") for i in range(8)]
    remote += [r(company="Remote 0", title="Solutions Engineer", posted="2026-10-03")]
    remote += [r(company="Remote 0", title="Customer Engineer", posted="2026-10-03")]
    visa = [r(company=f"Visa {i}", location="Dublin, Ireland", mode="onsite", visa=True)
            for i in range(3)]
    ranked = fr.rank(remote + visa, TODAY)
    rows = fr.table_rows(ranked, limit=10, per_company=2)
    companies = [row["use_case"] for row in rows]
    cases += 4
    check(failures, len(rows) == 10, f"{len(rows)} rows, expected 10")
    check(failures, sum(c.startswith("Visa") for c in companies) == 3,
          f"every visa-sponsoring role must get a seat when remote roles are plenty: {companies}")
    check(failures, companies.count("Remote 0") == 2, f"two roles a company at most: {companies}")
    check(failures, set(rows[0]) == {"use_case", "model", "maker", "access", "why", "url"},
          f"row keys: {sorted(rows[0])}")

    one = fr.table_rows([r(company="Anthropic", title="Forward Deployed Engineer",
                           location="London, UK", mode="onsite", visa=True, posted="2026-10-03",
                           url="https://job-boards.greenhouse.io/anthropic/jobs/1",
                           source="greenhouse:anthropic")])[0]
    cases += 4
    check(failures, one["why"] == "Posted 3 Oct on Anthropic's careers page.", f"why: {one['why']!r}")
    check(failures, one["maker"] == "London, UK" and one["access"] == "sponsors visas",
          f"place and visa: {one['maker']!r}, {one['access']!r}")
    check(failures, one["url"].endswith("/jobs/1"), "the row links to the posting")
    hn = fr.table_rows([r(source="hn", posted=None, location="Remote (Worldwide)")])[0]
    check(failures, hn["why"] == 'Posted date not given on Hacker News "Who is hiring?".'
          and hn["access"] == "", f"an HN remote row: {hn!r}")
    cases += 2
    check(failures, fr.visa_note(r(mode="onsite", visa=True, scope="Germany"))
          == "sponsors visas (Germany only)", "a scoped visa note names the country")
    check(failures, fr.visa_note(r(mode="onsite")) == "visa not stated",
          "an on-site role with no visa wording says so")

    # ── 6. Hacker News "Who is hiring?" posts ────────────────────────────────
    post = {"id": 41, "created_at": "2026-10-01T15:00:00Z",
            "text": "Acme AI | Forward Deployed Engineer | REMOTE (Worldwide) | VISA | Full-time"
                    "<p>We build LLM agents for banks."}
    got = fr.parse_hn_post(post)
    cases += 4
    check(failures, got and got["company"] == "Acme AI" and got["title"] == "Forward Deployed Engineer",
          f"HN company and title: {got!r}")
    check(failures, got and got["mode"] == "remote" and got["visa"] is True,
          f"HN remote and visa: {got!r}")
    check(failures, got and got["url"] == "https://news.ycombinator.com/item?id=41",
          "HN rows link to the comment")
    check(failures, got and "Full-time" not in got["location"] and "VISA" not in got["location"],
          f"HN place keeps only the place: {got and got['location']!r}")
    cases += 3
    onsite = dict(post, text="Acme AI | Solutions Engineer | ONSITE New York<p>LLM agents.")
    check(failures, fr.parse_hn_post(onsite) is None, "an on-site HN post without a visa is dropped")
    not_ai = dict(post, text="Shoe Co | Sales Engineer | REMOTE<p>We sell shoes online.")
    check(failures, fr.parse_hn_post(not_ai) is None, "an HN post that is not AI work is dropped")
    no_visa = fr.parse_hn_post(dict(post, text="Acme AI | Solutions Engineer | REMOTE | No visa"
                                               "<p>Generative AI for retail."))
    check(failures, no_visa and no_visa["visa"] is False, f"'No visa' is read as no: {no_visa!r}")

    # ── 7. Readers, fed each board's JSON shape ──────────────────────────────
    gh = fake_get({"boards/acme/jobs": {"jobs": [
        {"id": 7, "title": "Forward Deployed Engineer", "location": {"name": "London, UK"},
         "first_published": "2026-10-02T09:00:00-04:00",
         "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/7"},
        {"id": 8, "title": "Recruiter", "location": {"name": "Remote"},
         "absolute_url": "https://x/8"}]}})
    got = fr.read_greenhouse("Acme", "acme", get=gh)
    cases += 2
    check(failures, len(got) == 1 and got[0]["_id"] == 7 and got[0]["mode"] == "onsite"
          and got[0]["posted"] == "2026-10-02", f"greenhouse: {got!r}")
    detail = fake_get({"jobs/7": {"content": "&lt;p&gt;We can sponsor visas to Ireland.&lt;/p&gt;"}})
    check(failures, fr.greenhouse_visa("acme", 7, get=detail) == (True, "Ireland"),
          f"greenhouse visa from the posting text: {fr.greenhouse_visa('acme', 7, get=detail)}")

    ash = fake_get({"job-board/acme": {"jobs": [
        {"title": "Solutions Engineer", "location": "Remote - EMEA", "workplaceType": "Remote",
         "isRemote": True, "isListed": True, "publishedAt": "2026-10-01T10:00:00.000+00:00",
         "descriptionPlain": "Visa sponsorship is available.", "jobUrl": "https://jobs.ashbyhq.com/acme/1"},
        {"title": "Forward Deployed Engineer", "location": "NYC", "isListed": False,
         "jobUrl": "https://jobs.ashbyhq.com/acme/2"}]}})
    got = fr.read_ashby("Acme", "acme", get=ash)
    cases += 1
    check(failures, len(got) == 1 and got[0]["mode"] == "remote" and got[0]["visa"] is True,
          f"ashby (unlisted jobs skipped): {got!r}")

    lev = fake_get({"postings/acme": [
        {"text": "Forward Deployed Software Engineer", "categories": {"location": "Washington, D.C."},
         "workplaceType": "onsite", "createdAt": 1790936000000,
         "descriptionPlain": "We are unable to sponsor visas.", "hostedUrl": "https://jobs.lever.co/acme/1"}]})
    got = fr.read_lever("Acme", "acme", get=lev)
    cases += 1
    check(failures, len(got) == 1 and got[0]["visa"] is False and got[0]["mode"] == "onsite"
          and got[0]["posted"] == "2026-10-02", f"lever: {got!r}")

    him_job = {"guid": "g1", "title": "Forward Deployed Engineer", "companyName": "Vozy AI",
               "locationRestrictions": [], "pubDate": 1790985600, "excerpt": "Agents for support.",
               "applicationLink": "https://himalayas.app/companies/vozy/jobs/1"}
    him = fake_get({"himalayas.app": {"jobs": [
        him_job,
        dict(him_job, guid="g2", title="Solutions Engineer", companyName="Shoe Co"),
        dict(him_job, guid="g3", title="Solutions Engineer, AI Platform", companyName="Data Co",
             locationRestrictions=["United States", "Canada", "Mexico", "Brazil"])]}})
    got = fr.read_himalayas(get=him)
    cases += 3
    check(failures, [x["company"] for x in got] == ["Vozy AI", "Data Co"],
          f"himalayas: once per job across queries, AI roles only: {[x['company'] for x in got]}")
    check(failures, got and got[0]["location"] == "Remote (worldwide)", f"himalayas place: {got[:1]!r}")
    check(failures, len(got) > 1 and got[1]["location"] == "Remote (United States, Canada, Mexico and more)",
          f"himalayas long restriction list: {got[1:2]!r}")

    hn_get = fake_get({
        "search_by_date": {"hits": [{"title": "Ask HN: Who wants to be hired? (October 2026)",
                                     "objectID": "1"},
                                    {"title": "Ask HN: Who is hiring? (October 2026)",
                                     "objectID": "2"}]},
        "items/2": {"children": [post, onsite]}})
    got = fr.read_hn(get=hn_get)
    cases += 1
    check(failures, len(got) == 1 and got[0]["company"] == "Acme AI",
          f"read_hn reads the hiring thread, not the wants-to-be-hired one: {got!r}")

    # ── 8. One board down does not stop the rest ─────────────────────────────
    routes = {"boards/anthropic/jobs/7": {"content": "We sponsor visas."},
              "boards/anthropic/jobs": {"jobs": [
                  {"id": 7, "title": "Forward Deployed Engineer", "location": {"name": "London, UK"},
                   "first_published": "2026-10-03T09:00:00Z",
                   "absolute_url": "https://job-boards.greenhouse.io/anthropic/jobs/7"}]},
              "job-board/openai": ConnectionError("refused"),
              "search_by_date": {"hits": []}}
    roles, broken = fr.collect(TODAY, get=fake_get(routes))
    cases += 3
    check(failures, any(b.startswith("OpenAI (ashby): ConnectionError") for b in broken),
          f"a failed board is reported: {broken}")
    anth = [x for x in roles if x["company"] == "Anthropic"]
    check(failures, anth and anth[0]["visa"] is True,
          f"Greenhouse postings are read in full for visa wording: {anth!r}")
    check(failures, all("_id" not in x for x in roles), "the Greenhouse id is not written out")

    # ── 9. The builder's table, from .tmp/roles.json ─────────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "roles.json")
        today = builder_helpers.datetime.now().strftime("%Y-%m-%d")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"as_of": today, "roles": fr.rank(remote + visa, TODAY)}, f)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            table = builder_helpers.open_roles(roles_file=path)
            missing = builder_helpers.open_roles(roles_file=os.path.join(tmp, "none.json"))
    cases += 3
    check(failures, table and table["as_of"] == today and len(table["best_for"]) == 10,
          f"open_roles: {table and (table['as_of'], len(table['best_for']))}")
    check(failures, missing is None, "no roles file gives no table")
    check(failures, "find_roles.py" in buf.getvalue(), "a missing roles file says how to make it")

    # ── 10. The PDF draws the table, each role linked to its posting ─────────
    from generate_pdf import render_edition
    from pypdf import PdfReader
    pdf = render_edition({"sections": {}, "section_extras": {"fde_careers": table}})
    reader = PdfReader(io.BytesIO(bytes(pdf.output())))
    text = "".join(pg.extract_text() for pg in reader.pages)
    uris = {a.get_object()["/A"]["/URI"] for pg in reader.pages for a in pg.get("/Annots") or []
            if "/A" in a.get_object() and "/URI" in a.get_object()["/A"]}
    cases += 3
    check(failures, "OPEN ROLES" in text, "the careers table has its heading")
    check(failures, "Visa 0" in text and "sponsors visas" in text,
          "the careers table prints the company and its visa position")
    check(failures, {row["url"] for row in table["best_for"]} <= uris,
          "every role in the table links to its posting")

    for f in failures:
        print("FAIL:", f)
    print(f"{cases}/{cases} passed" if not failures else f"{len(failures)} failure(s) of {cases}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
