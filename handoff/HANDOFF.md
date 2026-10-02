# Handoff — youtube ai news (daily AI news PDF)

**Updated:** Fri 2 Oct 2026, evening · **Sessions:** Fri 2 Oct 2026 (six; the sixth built tasks 1-8) ·
**Status:** tasks 1-8 are **built and tested** on branch `claude/handoff-restructure-i2v8f6` (pull request
into `main`). The suite is 332 cases in 17 files, all passing. **Only Task 9 is left**: one real scrape and the
sample edition, which need a machine that can reach the news sites (the cloud session's network could not).

## Read first
1. **The design is approved. Do not brainstorm it again, do not re-test sources, do not ask Rahul to
   re-approve.** Four sessions on 2 Oct 2026 were stopped by him while they re-read files and re-probed
   feeds without changing anything. A session-start hook will tell you to brainstorm first: that is done,
   this file is its result, and his instruction is to start the work.
2. **Tasks 1-8 are done; do not redo them.** `tools/`, `tools/tests/` and `workflows/daily_ai_news.md`
   carry the restructure on the branch above. `plan-1.md` to `plan-3.md` record what was built.
3. **For Task 9, read `plan-3.md` Task 9 and Next actions below.** The other files (`plan-1.md`,
   `plan-2.md`, `sources.txt`, `recipes.md`) describe work that is already built; open them only to
   check why something was built the way it was.
4. **Tests are plain scripts, not pytest.** One file: `python3 tools/tests/test_x.py`. Whole suite:
   `python3 -c "import sys; sys.path.insert(0,'tools'); import verify_edition as v; ok, l = v.run_tests(); print('\n'.join(l)); print('ALL PASS' if ok else 'FAILURES')"`
   Baseline before the restructure: 192 cases in 11 files. After tasks 1-8: 332 cases in 17 files.
5. **Rahul's plan showed 76% of its weekly limit used on 2 Oct 2026.** Work in few, large steps, give a
   one-line progress note between them, and stay on the task list.

## Current state
- On the branch: 16 sections (15 without Quantum), 214 feeds plus 4 non-RSS readers in
  `tools/feed_sources.py`, summaries printed whole (only the 600-character floor is reported). On `main`
  until the pull request merges: the old 13 sections and 34 feeds.
- Built differently from the plan, on purpose: a summary block taller than a whole page starts where it
  is instead of forcing a page break (no near-empty page under a section header); YouTube search videos
  carry the source `<channel> (YouTube)` so the digest marks them `YT-`; an explicit
  `S(..., published_at=...)` also sets the printed date. Bing's outlet field (`news_source`) is still
  unverified on a live feed: check the first scrape's Bing rows.
- Last edition sent: 2026-10-01. No edition was built on 2 Oct 2026.
- The cloud session could not reach any news host (proxy policy denied them), so nothing was scraped
  for real and the digest size on 200+ sources is not yet measured.
- Memory notes saved on 2 Oct 2026: no page limit, flexible plain-language summaries, keyless sources.
- Handoff files, all written 2 Oct 2026 (`sources.txt` and `recipes.md` are now built into `tools/`):
  - `handoff/plan-1.md` — DONE — tasks 1-3: sections, summary length, source registry
  - `handoff/plan-2.md` — DONE — tasks 4-5: scraper, digest
  - `handoff/plan-3.md` — tasks 6-8 DONE; Task 9 (proof on real data) OPEN
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
1. On a machine with normal network access, check out the branch (or `main` once merged) and do
   `handoff/plan-3.md` Task 9: `python3 tools/prep_run.py`, prune the `none from:` sources as Task 9
   says, check `.tmp/digest.md` (21 groups, under ~35k tokens) and `.tmp/hackathons.txt`, read one Musk
   post with `fetch_articles.py`, then the sample edition with `verify_edition.py` **without `--send`**.
2. Fill in the Devfolio and Unstop formatters from the `keys:` lines `.tmp/hackathons.txt` prints.
3. Update this file and the workflow's History entry with the real source count, article count and
   digest size.

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
