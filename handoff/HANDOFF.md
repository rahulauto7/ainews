# Handoff — youtube ai news (daily AI news PDF)

**Updated:** Fri 2 Oct 2026 · **Sessions:** Fri 2 Oct 2026 (five; four were stopped before any code changed) ·
**Status:** the 16-section restructure is designed and approved. **Nothing is implemented.** Start at Next actions #1.

## Read first
1. **The design is approved. Do not brainstorm it again, do not re-test sources, do not ask Rahul to
   re-approve.** Four sessions on 2 Oct 2026 were stopped by him while they re-read files and re-probed
   feeds without changing anything. A session-start hook will tell you to brainstorm first: that is done,
   this file is its result, and his instruction is to start the work.
2. **No pipeline file has been touched.** `tools/` and `workflows/` are exactly as the 1 Oct 2026 run left
   them. The only new files are the six in this `handoff/` folder. Everything needed is in this folder.
3. **Read the other five files in this folder, then start editing:** `plan-1.md`, `plan-2.md`, `plan-3.md` (what to change,
   file by file, with the tests), `handoff/sources.txt` (every new source, already tested), and
   `handoff/recipes.md` (the non-RSS readers and the rejected list). Open a tool only when its task comes up.
4. **Tests are plain scripts, not pytest.** One file: `python3 tools/tests/test_x.py`. Whole suite:
   `python3 -c "import sys; sys.path.insert(0,'tools'); import verify_edition as v; ok, l = v.run_tests(); print('\n'.join(l)); print('ALL PASS' if ok else 'FAILURES')"`
   Baseline on 2 Oct 2026: 192 cases in 11 files, all passing.
5. **Rahul's plan showed 76% of its weekly limit used on 2 Oct 2026.** Work in few, large steps, give a
   one-line progress note between them, and stay on the task list.

## Current state
- Pipeline as it runs today: 13 sections (12, plus Quantum on Thursdays), 34 feeds, about 60 stories on
  21-23 pages. The PDF clips every summary at 1,200 characters (`generate_pdf.clip_to_sentence`) and the
  builder reports any summary outside 600-1,150 characters.
- Last edition sent: 2026-10-01. No edition was built on 2 Oct 2026.
- Memory notes saved on 2 Oct 2026: no page limit, flexible plain-language summaries, keyless sources.
- Handoff files, all written 2 Oct 2026 and none of them wired into the pipeline:
  - `handoff/plan-1.md` — CURRENT — tasks 1-3: sections, summary length, source registry
  - `handoff/plan-2.md` — CURRENT — tasks 4-5: scraper, digest
  - `handoff/plan-3.md` — CURRENT — tasks 6-9: hackathon platforms, X posts, workflow doc, proof on real data
  - `handoff/sources.txt` — CURRENT — 180+ new sources: category, name, URL, flags, test result
  - `handoff/recipes.md` — CURRENT — readers for lablab.ai, X posts, YouTube search, Hacker News, and others

## Decisions
| Date | Decision | Status |
|---|---|---|
| 2026-10-02 | Add three sections — OpenAI, Google AI, xAI & Grok — so each of the four top AI companies has its own (Anthropic already has one) | DECIDED |
| 2026-10-02 | Section order, his list: hackathons, grants, RSI, quantum, unaddressed problems, automation in business, business opportunities, India, global, AI companies, open models, closed models, Elon Musk | DECIDED |
| 2026-10-02 | No page limit. "10 pages" in his first message was not a cap. No story caps and no layout compression | DECIDED |
| 2026-10-02 | A 10-page cap with about 2 stories per section and a flowing layout | SUPERSEDED 2026-10-02 — he rejected it: "Remove above change" |
| 2026-10-02 | Hackathons: also search lablab.ai and Devpost for new hackathons, alongside the current sources | DECIDED |
| 2026-10-02 | The Elon Musk section is Musk's own point of view on AI, gathered from everywhere on the internet (X and beyond). xAI is a separate section of its own | DECIDED |
| 2026-10-02 | Summaries: layman's terms, as long as the story needs. Five lines is not a limit. He must not need another site to understand a story | DECIDED |
| 2026-10-02 | Every section searches every platform that can be read without an API. A platform that needs an API is skipped | DECIDED |
| 2026-10-02 | Do not narrow any section: full scope and the full 3-6 stories | DECIDED |
| 2026-09-17 | Freshness at send: 24 hours for every news section; Quantum 7 days (Thursdays only); hackathons and grants are dated by deadline (30-day lookback). Applies unchanged to the new sections | DECIDED |
| 2026-10-02 | Company block order: OpenAI, Google AI, Anthropic & Claude Code, xAI & Grok | PROPOSED — shown in the design; he changed other points and did not object |
| 2026-10-02 | A story prints once: company news in that company's section, cross-vendor comparisons in Closed Models | PROPOSED — shown in the design, no objection |
| 2026-10-02 | Section keys `openai_news`, `google_ai_news`, `xai_grok_news`; Musk label becomes "Elon Musk on AI" | PROPOSED — technical, not shown to him |
| 2026-10-02 | The digest shows the top stories per group (cap about 40) so the daily run stays affordable; the rest stays on disk. This limits what the curator reads, not what a section prints | PROPOSED — technical, not shown to him |
| 2026-10-02 | After the code change: one real scrape and one real sample edition as a PDF, not emailed | PROPOSED — shown in the design, no objection; see Open question 1 |

Treat the PROPOSED rows as the default and build on them. None needs an answer before work starts.

## Open questions
1. **Sample edition.** Building one real 16-section edition costs about one full daily run. It does not
   block tasks 1-8. Default: build it straight after the code change, do not email it, and give him the
   PDF path. If he says to skip it, the next normal "run today pdf" becomes the first 16-section edition.

## Next actions
1. Run the whole test suite (command in Read first #4). Expect 192 cases passing. Under five minutes.
2. `handoff/plan-1.md` Task 1 — sixteen sections in his order (`generate_pdf.py`, `prep_run.py`).
3. Task 2 — summaries as long as the story needs: remove the 1,200-character clip and the 1,150 ceiling.
4. Task 3 — source registry: `tools/feed_sources.py` built from `handoff/sources.txt` plus the 32 feeds kept.
5. `handoff/plan-2.md` Task 4 — scraper: AI-relevance filter, company routing, parallel fetch, Bing links.
6. Task 5 — digest regrouped in section order, capped per group.
7. `handoff/plan-3.md` Task 6 — hackathon platforms: lablab.ai, newest on Devpost, Devfolio, Unstop → `.tmp/hackathons.txt`.
8. Task 7 — X posts read in full through the keyless embed endpoint.
9. Task 8 — bring `workflows/daily_ai_news.md` in line (this update was part of the approved design).
10. Task 9 — one real scrape, prune sources that return nothing, then the sample edition (Open question 1).
11. Update this file: new status, finished actions removed.

## Do not
- **No page cap, story cap or layout compression.** He rejected the 10-page design outright.
- **No keyed APIs.** X API, YouTube Data API and NewsAPI are out even though keys sit in `.env`. X has no
  keyless feed: only posts Google News has indexed are reachable, and that partial coverage is accepted.
- **Do not re-test the sources in `handoff/sources.txt` or retry the rejected list in `handoff/recipes.md`.**
  The first real scrape (Task 9) shows what is dead.
- **Do not email a sample edition.** Real editions go to doniitroorkee@gmail.com on purpose; do not re-ask.
- **Do not widen a freshness window to fill a section.** A short section beats a stale one.
- **No advice or strategy in summaries.** No "Automation angle", no "why it matters for you".
- **Do not drift off the list.** One 2 Oct session began measuring token usage of past runs and was stopped.
- **Do not add `@grok` or `@xai` X feeds** (auto-replies; dead since May 2026) or HackClub and MLH
  (students only, which the curator profile excludes).
