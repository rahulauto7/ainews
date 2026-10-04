# Daily AI News Pipeline — Master Workflow

## Objective
Generate and deliver a daily AI news PDF covering **16 sections** to Gmail by 7:00 AM IST.
Channel focus is **AI automation**, but the summaries themselves are written as plain, self-contained
news explanations — see the **Plain-Language News Rule**.

**Quantum + AI is weekly (Thursdays only).** On Fri–Wed the pipeline runs 15 sections.
`QUANTUM_WEEKDAY = 3` in `scrape_rss_feeds.py` is authoritative; `prep_run.py` prints which way today
falls, so it never has to be worked out by hand.

**Every story explained in full, fifteen pages at most.** Rahul, 2026-10-03: "I want a clear
understanding, in layman's terms, a news summary, no matter how long it takes in lines", because the
400–800 character summaries of 2026-10-02 gave him five lines a story and sent him elsewhere to
understand them. Asked the same day whether to keep the page limit, he chose **max 15 pages**. So:
**every summary is a full plain-language explanation of at least 1,000 characters with no upper
limit** (see the Plain-Language News Rule), and the page limit is met by carrying **fewer stories,
2–4 a section, usually 3**, never by shortening an explanation. Three 2,000-character stories a
section is 14 pages on a weekday and 15 on a Thursday. Page 1 opens with a short masthead and a
contents list (each entry links to its section and names its page), the sections flow on from each
other, a long story runs on overleaf like a newspaper column, and story URLs sit behind the titles.
`write_analyzed()` prints the page count while the builder is open and, over the limit, names the
stories to drop; `verify_edition.py` blocks the send above `PAGE_LIMIT` (15, in `generate_pdf.py`).

---

## The 24-Hour Rule (hard)

**Nothing older than 24 hours reaches the inbox**, with one deliberate exception: the weekly
quantum section runs a 7-day rule. Opportunities are dated by deadline and sit outside this
entirely. Nothing else gets a pass.

The rule is measured **at send**, not at scrape. That distinction is the whole point: on 2026-09-17
the scrape cut correctly at 24h from `scraped_at` (00:04 UTC), but the edition was not mailed until
15:39 UTC, so **34 of its 44 news stories arrived over 24 hours old** while every scrape-side check
still read clean. A window anchored to the wrong end of the pipeline is not a window.

Three things hold the rule up, and none of them needs a judgement call:

| Constant / check | Where | What it does |
|---|---|---|
| `NEWS_RULE_HOURS = 24` | `scrape_rss_feeds.py` | The promise. Must equal `check_quality.STALE_HOURS` — a test fails if they drift. |
| `QUANTUM_RULE_HOURS = 168` | `scrape_rss_feeds.py` | The one news exception, 7 days. Must equal `check_quality.SECTION_STALE_HOURS["quantum_ai_research"]`. |
| `BUILD_ALLOWANCE_HOURS = 2` | `scrape_rss_feeds.py` | Reserved for curate + render + verify + send. Each scrape window is its rule **minus** this — 22h for news, 166h for quantum — so the oldest article the scraper hands you is still inside the rule two hours later. |
| `stale_story` (ERROR) | `check_quality.py` | Re-measures every story against the clock at send, **against its own section's rule**. **Blocks the send.** |

`verify_edition.py` step 4 prints one line per rule in play, e.g.
`freshness: oldest of 49 stories on the 24h rule is 16.6h old`.

**The three tiers, and why they differ:**

| Sections | Rule | Why |
|---|---|---|
| Every news section | **24h** | The promise. No exceptions, no "it's too good to drop". |
| `quantum_ai_research` | **7 days** | The section is **weekly (Thursdays)**, so each issue covers the whole week since the last one. 24h would leave it empty every Thursday. Wider, not absent — a quantum story over 7 days old still blocks the send. |
| `OPPORTUNITY_KEYS` | **exempt** (30-day scrape) | A hackathon is dated by the **deadline it is still open against**, not by the day it was announced. A 24h window empties the section outright (2026-09-07). |

`ai_business_opportunities` is a **news** section despite the name — it carries stories, not deadlines,
so it is bound by the 24h rule like the rest.

**If the run drags past the allowance, it blocks itself.** That is the intended behaviour. Re-run
`prep_run.py` for a fresh scrape rather than forcing a stale edition through.

**Curating:** `S()` copies the full `published_at` timestamp, not just the date, because a date alone
cannot tell 01:00 from 23:00 — a 22-hour spread, most of the window the rule allows. `write_analyzed()`
flags a stale pick while the builder is still open, so it never gets as far as a blocked send.

---

## The Run: two commands and the curation between them

The mechanical work is in two tools. Everything they print is what the next step needs; nothing in
between them requires a model.

```
python3 tools/prep_run.py          # ~15s  — everything before curation
   ↓  curate (the only agent-driven step)
python3 tools/verify_edition.py --send    # ~10s — every check, the backup, the send
```

### Step 1 — `python3 tools/prep_run.py`
Runs the scrape to completion (nothing is detached, so nothing needs polling), then the digest,
Devpost, the carry-forward recheck and the other hackathon platforms **in parallel with the test
suite**, and prints one brief: today's date and whether Quantum is in, the 16 section keys in render
order, the last three editions on disk for the duplicate check, and the test result as one line.

The scrape reads every source in the registry, `tools/feed_sources.py`: 386 RSS and Atom feeds plus
four non-RSS readers (Hacker News, Hugging Face new models, two YouTube searches), all keyless
(rahul, 2026-10-03: "search everywhere on the internet ... if they are asking for any API, don't use
that platform"). That is mainstream, wire, trade, science and regional press; Google News searches in
14 English-language country editions and in 17 other languages; Bing News; YouTube channels and
podcasts; Reddit and Bluesky. Hosts are fetched in parallel; the 80 Google News searches share one
host and run in turn, about two minutes. A feed that answers 403, 429 or 503 is retried once with the
browser User-Agent. `.tmp/rss_scrape.log` ends with `Sources: N read, M returned articles` and a
`none from:` line.

Outputs: `.tmp/rss_articles.json`, `.tmp/digest.md`, `.tmp/devpost.txt`, `.tmp/recheck.txt`,
`.tmp/hackathons.txt`.

- `--no-scrape` reuses the scrape on disk. A scrape under 6 hours old is reused automatically, so a
  second run the same morning does not re-hit 200+ sources; the next day's run always re-scrapes.
- If the scrape fails, it stops there — the scrape is the only input source.

### Step 2 — Curate (agent-driven; the only step that needs a session)
1. **Read `.tmp/digest.md`.** One line per article, grouped in the order of the 16 sections (each
   group's heading names its section after `->`), biggest story first and direct feeds before search
   proxies, `PRINTED mm-dd` on anything from the last three editions, `{also: ...}` on a story that
   fits more than one group, gate-passing opportunities, and yesterday's opportunities, `best_for`
   table and rejection log. **Each group is capped** (40; general 60; world 50; non-English 30; video 30; research, social
   and forums 25)
   and ends `(+K more in rss_articles.json, not shown)`: the cap limits what you read, never how many
   stories a section prints. Aim to keep the file under ~35k tokens; `prep_run.py` prints its size.
   Two groups are new on 2026-10-03: **non-English press** (Global AI News; summarise in English and
   give the story an English title with `S(..., title=...)`, since characters outside latin-1 print
   as `?`) and **Reddit and Bluesky** (leads: write up the release or article a post points to).
2. **`python3 tools/fetch_articles.py IDX IDX ...`** for the shortlist. Decodes Google News proxy
   links, fetches publisher pages in parallel, caches under `.tmp/articles/`, flags
   `OLD` / `THIN` / `FAILED` / `X POST`. **Batch it** — one call with 20 indices is one turn.
   The excerpt is **5,000 characters** by default, enough of most articles to explain the story in
   full; `--chars 0` prints status lines only. **A blocked, paywalled or empty page is read from
   another outlet automatically**: first the other outlets the scrape found carrying the story, then
   a keyless Google News search of the headline. The head line then says `read via <outlet>: URL`;
   pass that URL and outlet to `S(..., url=..., source=...)` so the title links to a page the reader
   can open. `own page FAILED, no other outlet found` means the story really is headline-only.
   **X posts are read in full** through the keyless embed endpoint: the whole post, any quoted post,
   the reply line, and the post's own timestamp on the head line. Pass that timestamp to
   `S(..., published_at=...)` so the 24h rule measures the post, not the day Google indexed it. The
   `X POST` flag now means the read failed and the feed headline is all there is. It is not cached, so
   running the index again retries it.
3. **`.tmp/devpost.txt`, `.tmp/hackathons.txt` and `.tmp/recheck.txt`** are already on disk from
   step 1, for sections 1–2.
   `python3 tools/find_opportunities.py check URL...` is the only one that runs on demand, for an
   opportunity neither file covers.
4. **Write `.tmp/build_analyzed_<DATE>.py`** against `tools/builder_helpers.py` (`S`, `O`,
   `carry_forward_best_for`, `write_analyzed`). **Its docstring is the format — do not open an old
   builder to copy boilerplate.** Reference source articles **by index** into `rss_articles.json` so
   title/url/source stay faithful to what was scraped; never hand-type a URL. `write_analyzed()`
   validates section counts, summary lengths, missing URLs and `published_date`, renders the PDF to
   count its pages, and prints the problems. Over 15 pages it prints `to fit, drop:` with the
   lowest-relevance stories from the fullest sections; drop those (or others of your choosing), never
   shorten an explanation. Write a long summary in two or three paragraphs, separated by a blank
   line inside the `'''` quotes; the PDF prints the break. `rejected=[(name, reason)]` feeds tomorrow's digest so a rejected item is not
   re-investigated.

### Step 3 — `python3 tools/verify_edition.py --send`
In order, stopping the run where noted: test suite (fail → stop) → render the PDF (fail → stop) →
rendered-text checks (fail → stop) → quality review (ERROR → stop, WARN → print) → backup → send.

The rendered-text checks are the ones that used to be done by eye, and each is now arithmetic:
- **Stray `?`** — counts the PDF's question marks against the source JSON's. Any excess is a
  character `sanitize_text()` could not map to latin-1. Grepping for `?` could never tell that from
  a real question, which is why the same three sentences were re-read every run.
- **Unfinished summaries** — flags any summary not ending on a complete sentence.
- **Missing titles** — every story title must appear in the rendered page. Compared on a squashed
  30-character prefix, because `sanitize_text()` folds curly apostrophes, `multi_cell()` wraps
  titles across lines and `_fit_title()` truncates the longest ones.
- **Page count** — over `PAGE_LIMIT` (15) stops the run. Drop the stories `write_analyzed()` named
  under `to fit, drop:` (the lowest-relevance stories from the fullest sections), rebuild, and verify
  again. Never shorten an explanation to fit (rahul, 2026-10-03).

Flags: `--skip-pdf` (already rendered this run), `--skip-tests`, and no `--send` to verify and back
up without mailing.

**The backup is taken here, as soon as the PDF verifies** — not at the start of the next run. Taking
it late is what let the 2026-09-15 edition vanish untraced.

### Delivery
`send_email.py` via Gmail OAuth. Recipient is `RECIPIENT_EMAIL` in `.env`; the body is generated from
`analyzed_content.json` at send time, so the section list and counts are always the real ones.
One-off override: `RECIPIENT_EMAIL=foo@bar.com python3 tools/send_email.py`.

**Cloud routine runs send from GitHub, not from the Claude session.** Claude cloud sessions in this
project get linked to rahul's computer, and a linked session cannot reach `oauth2.googleapis.com`, so
the Gmail token never refreshes there (found 2026-10-03). In a routine run, run
`verify_edition.py` **without** `--send`, push the backup to the archive branch
(`claude/daily-news-editions-2hw8xn`, `editions/analyzed_content_<DATE>.bak.json`), then start the
**Send daily edition** GitHub Actions workflow (`.github/workflows/send_edition.yml`, on `main`). It
re-runs every check against the archived edition and mails it with the `GMAIL_TOKEN_JSON` and
`RECIPIENT_EMAIL` repository secrets. It also runs by itself at 06:40 IST as a fallback, and a
`editions/sent_<DATE>.txt` marker on the archive branch keeps it to one mail a day (rerun with
`force` to send again). Since it re-measures freshness at send, start it as soon as the backup is pushed.
The access token expires hourly and refreshes itself from `token.json`; only a revoked refresh token
needs a browser.

---

## The 16 PDF Sections
In render order, Rahul's list of 2026-10-02. `prep_run.py` prints the keys, so they are never guessed:

1. **AI Hackathons** — high-prize AI hackathons and competitions with entry deadlines, globally
   scoped, open to professionals and founders, whose **submission deadline is at least 7 days away**
2. **AI Grants, Fellowships & Programs** — grants, fellowships, accelerators, incubators,
   residencies and cohort programmes
3. **AI Self-Improvement (RSI)** — recursive self-improvement, AGI progress, alignment research
4. **Quantum + AI** — *weekly, Thursdays only* — quantum breakthroughs where AI is genuinely involved
5. **Unaddressed AI Problems** — real pain points nobody is solving — market gaps
6. **AI Automation & Business** — AI automation news, agentic tooling, market demand
7. **AI Business Opportunities** — emerging opportunities — India & world
8. **Indian AI Industry** — India-specific AI news, policy, startups, government
9. **Global AI News** — worldwide AI: US, EU, China, Japan, Korea, Middle East
10. **OpenAI** — OpenAI and ChatGPT: models, products, research, deals, people and policy
11. **Google AI** — Google, Gemini and DeepMind: models, products, research and company moves
12. **Anthropic & Claude Code** — Claude models, Claude Code, Agent SDK, Anthropic company & safety news
13. **xAI & Grok** — xAI the company and its Grok models: releases, features, funding, deals, disputes
14. **Open Models & Open Weights** — open-weight releases, licences & benchmarks, plus a standing
    "best open model for what" table
15. **Closed Models & Frontier APIs** — proprietary frontier models: releases, pricing & benchmarks,
    plus a standing "best closed model for what" table
16. **Elon Musk on AI** — Musk's own point of view on AI, from his posts and from across the web

**Routing rule: a story prints once.** Company news goes to that company's section (10–13). A
cross-vendor comparison, benchmark or price table goes to Closed Models; an open-weight release goes
to Open Models whoever made it. What Musk himself says goes to Elon Musk on AI; xAI company and
product news goes to xAI & Grok. Global AI News takes the rest: governments, Meta, Microsoft, NVIDIA,
Apple, Chinese labs. The scraper pre-sorts the digest the same way (a pooled headline naming OpenAI,
Google, Anthropic, xAI or Musk moves into that group), but the curator decides.

---

## Plain-Language News Rule
Summaries explain **the news itself**, in everyday language a reader with no background in the topic
can follow, **as fully as the story needs, however many lines that takes**. The test (rahul,
2026-10-03): after reading only that summary, he understands the story and never has to look
elsewhere. They are news explanations, not strategy notes, and they carry no advice.

**How to apply** — every summary does these five things, woven into flowing prose with **no headings
or bold labels inside the summary**, in two or three paragraphs when it runs long:
1. **Say what happened.** Lead with the actual event, not with its implications.
2. **Explain every name and term at first mention.** Who a person is, what a company does, what a
   product or technical term means — inline, in a clause or in brackets. Assume the reader has never
   heard of PhonePe, OAuth, prompt caching, a tensor network or a fractal dimension.
3. **Explain why the news exists.** The situation, pressure or history that produced the event, so it
   makes sense instead of merely being reported.
4. **Explain how it works.** The mechanism in everyday words: what the product actually does, how the
   deal or rule operates, what the research found and how. An everyday comparison helps when it is
   accurate ("like a spell-checker for code").
5. **Say what changes and what comes next, as reported.** Who is affected and how, the next date or
   step the source names, and what is still unknown. Numbers get context (bigger or smaller than
   what, compared with last year). This is reporting, not advice.

**Write it plainly:** short sentences (one idea each; `check_quality` flags any over 45 words),
common words, active voice. Read the whole article first (`fetch_articles.py` prints 5,000
characters, and reads another outlet when the publisher blocks it), so the explanation comes from
the reporting rather than from the headline.

**Do NOT include**: `Automation angle:` hooks, "why it matters for you" blocks, "the opportunity
is..." framing, or suggestions about what to build. Removed 2026-09-03 on user instruction —
summaries had become strategy essays that assumed context the reader did not have, and the news
itself got lost.

### Summary Quality Rules
- **Explanatory, not a headline restatement.** Explain the *mechanism*. A reader who never opens the
  link should understand both what happened and why.
- **No unexplained jargon and no unexplained names.** If a term, person or company appears, it is
  defined in the same sentence. This is the most common failure mode and the one that made the
  2026-09-03 first draft unreadable. `check_quality.py` flags ALL-CAPS acronyms it cannot find
  spelled out, and runs inside `verify_edition.py`.
- **At least 1,000 characters and seven sentences, with no upper limit** (2026-10-03). Most stories
  need 1,200–2,500 characters to cover the five parts above; a complicated one may need more, and
  that is fine. The test: could he explain the story to someone else after reading only that
  summary? Never spend characters on advice. The PDF prints every summary whole; no ellipses, no
  mid-sentence cutoffs. `write_analyzed()` flags a summary under 1,000 characters, and
  `check_quality` blocks the send on one (`short_summary`).
- **Fifteen pages is the limit; pick, don't squeeze.** 2–4 stories per section, usually 3, the ones
  that matter most. When the edition runs over, drop stories; never shorten an explanation.
  A section runs short only when nothing else inside its freshness window qualifies. Finish every
  section; no placeholder stubs in trailing sections.
- **Do not invent facts.** Many headlines postdate the model's knowledge. Ground claims in what the
  feed actually says, attribute to the source, and build the explanation around the mechanism rather
  than inventing details.

---

## Curator Profile (applies to sections 1 & 2)
Only include items where **both team members** are eligible:

- Team A: employed at a company (working professional, adult, no PhD)
- Team B: BSc + MSc in Mathematics, currently unemployed / not enrolled anywhere, adult
- They live together, share income (A's salary supports B), long-term goal is a startup
- Relocation for a programme is fine; a stipend/salary is optional

**Reject:** items requiring a doctor, a PhD, current university enrolment, specific citizenship,
"students only" status (Google Cloud AI Builder Cup allows non-student non-employed team members if
the registrant is a working professional), or age/gender/geographic restrictions that exclude either
member. Region-locked programmes (Kenya-only, Nigeria-only, Kurdistan-only) are out.

**Near-deadline rule (section 2 only):** programmes whose deadline is tomorrow or later today MUST be
included — this outranks the three-day-repeat rule. The reader wants imminent deadlines, not silent
filtering. **Hackathons follow the opposite rule** (rahul, 2026-10-03, see `ai_hackathons` below): one
whose submission deadline is under 7 days away is left out, because there is no time left to build.

---

## Output JSON Schema
```json
{
  "analyzed_at": "<ISO 8601>",
  "total_items_analyzed": 0,
  "sections": { "<section_key>": [{ "title": "", "summary": "", "source": "", "url": "",
                                    "published_date": "YYYY-MM-DD", "relevance": 1, "tags": [] }] },
  "section_labels": { "<section_key>": "Display Name" },
  "section_extras": { "open_model_landscape": { "as_of": "YYYY-MM-DD", "best_for": [
    { "use_case": "", "model": "", "maker": "", "licence": "", "why": "" }
  ] } }
}
```

`published_date` is required on every news story and is copied from the source article by `S()`;
`write_analyzed()` rejects an edition missing it. Opportunity sections (1 and 2) carry a deadline
instead and the renderer skips dates there.

### Section-Specific Extra Fields
- `unaddressed_ai_problems`: `who_affected`, `severity` (critical/high/medium)
- `product_showcase_opportunities` / `ai_hackathons`: `opportunity_type`, `deadline`, `apply_url`,
  `prize`, `eligibility` — all optional. They render in that order and are dropped from the tail when
  the line will not fit, so a blank field costs nothing but a wrong one is published. **Except
  `deadline` on `ai_hackathons`, which is required:** it is the *submission* deadline written as a date
  ("23 Oct 2026"), and the 7-day build rule is checked against it.
- `open_model_landscape`: owns the `section_extras` block above. Optional — omit it and the section
  renders as plain news.

---

## Section-Specific Rules
**All sections:** 2–4 stories, usually 3, sorted by relevance (highest first).
Deduplicate across sources — the
Google News proxies return the same story from a dozen outlets, so pick the most substantive one.

- **`quantum_ai_research`** — *Thursdays only, and the one section on a **7-day** rule* rather than
  24h (see **The 24-Hour Rule**), because it is weekly and each issue covers the whole week since the
  last one. Seven days is still a limit: older papers block the send. Only stories where AI/ML is
  genuinely involved; skip pure quantum physics. arXiv quant-ph is the main source, so look for quantum machine learning,
  learned noise models and quantum representation learning rather than general quantum theory.

- **`ai_hackathons`** — hackathons, coding contests and time-boxed competitions with a defined prize
  pool and submission window. If it is not called a hackathon/competition/contest and awards no
  prize, it belongs in section 2. Sort by **prize size** after the eligibility filter, not by
  general relevance. Global, no geographic weighting.
  - **Biggest prize first (rahul, 2026-10-03: "in PDF, give me hackathons with our top prizes
    first").** `generate_pdf.render_edition()` prints the section in prize order whatever order the
    builder wrote, using `hackathon_sources.prize_usd()`: the largest cash amount in `prize`, roughly
    in dollars (`$`, `€`, `£`, `₹`, USD/EUR/INR/USDC, k/M/lakh/crore); amounts followed by "credits"
    do not count. So write the cash total in `prize` ("$138k cash total ($25k 1st)"); a hackathon
    with no `prize` prints last. When choosing among candidates, prefer the biggest verified cash
    prizes. Cases in `test_hackathon_prizes.py`.
  - **The 7-day build rule (rahul, 2026-10-03): "7 days is for build time ... exclude within 7 days
    submissions deadline not registration deadline".** Print a hackathon only when its **submission**
    deadline is at least 7 days after the edition date (7 exactly is enough). A registration deadline
    never counts, early or late: put the submission deadline in `deadline`, as a date ("23 Oct 2026";
    a time or a range is fine, the last date written is read). A hackathon whose submission deadline
    cannot be found is not printed. `check_quality.py` blocks the send on `hackathon_too_soon` and
    `hackathon_no_deadline`, and `write_analyzed()` reports both while the builder is open. The rule is
    in `hackathon_sources.MIN_BUILD_DAYS`; cases in `test_build_window.py`.
  - The candidate files apply the rule already: `devpost.txt`, `hackathons.txt` and each lablab block
    hide events closing in under 7 days (and say how many), and `recheck.txt` marks a carried-forward
    hackathon `UNDER 7 DAYS - drop`. A deadline only gets closer, so yesterday's 8-day entry is today's
    7 and tomorrow's 6: recheck before carrying one forward.
  - The scraper does not distinguish hackathons from grants — everything tagged `is_opportunity=True`
    is a candidate for both sections. Split them at curation by entry mechanism.
  - **Verify prize amounts against the organiser's own page.** Aggregators routinely quote non-cash
    reward totals ("$1M in prizes") that dwarf the actual cash prize ($3k first place). GatewayHacks
    2026 was rejected on 2026-09-12 for exactly this; `.tmp/devpost.txt` prints cash counts, but the
    `/rules` page is what settles it.
  - **`.tmp/hackathons.txt`** (`find_opportunities.py platforms`) lists AI hackathons from every
    other platform that can be read without an API key (rahul, 2026-10-03: search every platform, but
    skip any that asks for an API): lablab.ai's open events, soonest end first, each followed by the
    prize, eligibility and deadline lines of its own page; Devpost's newest "AI" events outside the
    theme listing; then mlcontests.com (Kaggle, AIcrowd, DrivenData, Zindi, CodaLab, Codabench and
    more), HackerEarth, Devfolio, Unstop, MLH, TAIKAI and Hackster, biggest prize first (then
    soonest deadline), each block ending with how many it hid as not AI or under 7 days. "submissions close" means the
    platform gives the submission deadline; "ends" means it gives only the event's end, the latest
    a submission can be due, so confirm the submission date on the event page before printing. Lines
    carry `printed mm-dd` / `rejected mm-dd: reason` as in `devpost.txt`. lablab prize lines often mix
    cash and credits ("$5k cash + $5k credits"), so the event page decides. Unstop and Devfolio are
    mostly Indian college events, often students-only, so the eligibility rules weed most of them out.
    The readers live in `tools/hackathon_sources.py` (cases: `test_hackathon_platforms.py`). The
    eligibility rules and the cash-prize check are unchanged.

- **`product_showcase_opportunities`** — longer-form commitments: accelerators, incubators,
  fellowships, residencies, grants, cohort programmes. Global, ranked on merit, not region.
  - **Excluded, however AI-related:** launch platforms and directories (Product Hunt), community
    forums (r/LocalLLaMA), open-source contribution channels, benchmark infrastructure, arXiv papers,
    market-thesis commentary. They fail the gate because there is nothing to enter.
  - Sources: the four `OPPORTUNITY_SOURCES` queries on a **30-day window** — an opportunity is dated
    by its deadline, not its announcement, so a 24h window returns nothing.
  - `qualifies_as_opportunity()` tags each entry `is_opportunity`. Filter on that field rather than
    re-deriving the rule. Cases: `tools/tests/test_opportunity_gate.py`.
  - **VERIFY EVERY DEADLINE BEFORE PUBLISHING.** The gate cannot tell an open opportunity from a
    closed one, and the 30-day window guarantees some have expired. On 2026-09-07 three of ten
    shortlisted items were already closed. Check the organiser's own page, not the article — and
    trust a Devpost status line over its dates.
  - **Back-fill by web search** when fewer than 4 entries survive verification. Search for open
    deadlines directly ("AI hackathon deadline October 2026") rather than filtering announcements.
    Listicle sites are mostly parked domains — go to the organiser or the registration page.
  - Never invent a deadline, prize or apply link. Leave the field out; the renderer omits blanks.
  - **Duplicate-across-days check.** The 30-day window guarantees an opportunity keeps surfacing
    until its deadline passes. `prep_run.py` prints the last three editions and the digest marks
    `PRINTED mm-dd`. Swap in at least one fresh entry per section; a carry-forward is acceptable when
    nothing new displaces it, but three-day repeats are the failure mode to avoid.

- **`anthropic_claude_news`** — Claude models, Claude Code, Agent SDK, Anthropic company and safety
  news. The proxy returns ~80/day with heavy duplication; cluster by story before selecting.

- **`open_model_landscape`** — models whose **weights are downloadable** (Llama, Qwen, DeepSeek,
  Mistral, Gemma, Kimi, GLM, OLMo, Falcon) plus their licences, benchmarks and tooling. A model
  reachable only through an API is not an open model. r/LocalLLaMA is the highest-yield source but is
  a forum: link and summarise the **release being discussed**, not the thread reacting to it.
  - The `best_for` table goes stale fastest, so: **5 rows, fixed use cases** — Coding, Long context,
    Runs on one GPU, Reasoning & math, Multilingual & Indic — so today's edition is comparable with
    last week's. **Ground every row in evidence** that actually came through the feeds; a leaderboard
    position remembered from training data is exactly the invented fact the rule above is about.
    **Carry a row forward unchanged** when nothing displaced it — that is the normal case, not a
    failure. **Stamp `as_of`** with the date the table was last actually revised, not today's.
  - `why` is one plain sentence on what makes that model best at that job. `licence` matters because
    "open" ranges from MIT to licences forbidding commercial use, and the reader cannot tell from the
    model name.

- **`ai_business_opportunities`** — the market-thesis section: emerging business openings, not things
  to apply to. Anything with an entry deadline belongs in section 2. Be specific about India.

- **`openai_news`** — OpenAI and ChatGPT: models, products, research, deals, people and policy.
  Sources: OpenAI's blog and YouTube, Google News and Bing News searches, and the X searches for
  @sama, @OpenAI and @OpenAIDevs. A cross-vendor benchmark or price comparison goes to Closed Models.

- **`google_ai_news`** — Google, Gemini and DeepMind: models, products, research and company moves.
  Sources: the Google AI, DeepMind, Research, Gemini and Cloud AI blogs, two YouTube channels, news
  searches, and the X searches for @GoogleDeepMind, @GoogleAI, @sundarpichai and @demishassabis.
  An open-weight Gemma release goes to Open Models.

- **`xai_grok_news`** — xAI the company and its Grok models: releases, features, funding, deals and
  disputes. x.ai has no feed and @xai/@grok are not usable on X (see Known Feed Issues), so the
  section runs on news searches and Tesla's YouTube channel. What Musk himself says about AI goes to
  the Musk section instead.

- **`elon_musk_ai_vision`** (label "Elon Musk on AI") — **Musk's own point of view on AI**: his X
  posts, interviews, podcasts, talks, and statements the press reports. Say what he actually said and
  the context it was said in. **Read each post in full** with `fetch_articles.py` and date it by the
  post's own timestamp (`S(..., published_at=...)`), not by the day Google indexed it. Sources: the
  X searches of x.com/elonmusk, Musk-on-AI news searches, Teslarati and Electrek (Musk-on-AI stories
  only), and a YouTube search. Preserve post URLs.

---

## Hackathon Alerts (hourly email, separate from the PDF)
rahul, 2026-10-03: "make a scheduler who check popular hackathon sites for the moment hackathon
launched it will email me" (at rahularebhai@gmail.com). This is **not** part of the daily run and needs
no session:

- **`.github/workflows/hackathon_alerts.yml`** runs `tools/hackathon_watch.py` every hour (at :23) on
  GitHub Actions. It reads the platforms in `hackathon_sources.py` and emails each AI hackathon it has
  not seen before that anyone can enter and that leaves 7+ days before the submission deadline (one
  with no deadline listed is sent too, marked "Deadline not listed"). Several new ones go in one email,
  soonest deadline first. **HackerEarth is not watched:** its event feed answers 403 to GitHub's
  runners (first dry run, 2026-10-03) though a Claude session reads it, and its listing page renders
  in the browser. It stays in `.tmp/hackathons.txt` for the PDF (`NOT_FROM_GITHUB` in the watcher).
- **Why GitHub and not a Claude routine:** Claude cloud sessions in this project get linked to rahul's
  computer and then cannot sign in to Gmail (2026-10-03), and a routine draws on rahul's plan usage.
- **Why hourly:** the repository is private, so Actions minutes count against the free 2,000 a month;
  an hourly run bills one minute, about 720 a month beside the daily edition's send.
- **Mail** goes through the Gmail API with the `GMAIL_TOKEN_JSON` repository secret, the same one the
  daily edition's send uses. The recipient defaults to rahularebhai@gmail.com; the repository variable
  `HACKATHON_ALERT_EMAIL` overrides it. Without the secret the run skips with a warning.
- **The seen-list** is `seen.json` on the `hackathon-alerts-state` branch, committed only when it
  changes. The first run sends one welcome email listing everything open; a platform read for the
  first time later is recorded quietly, so it never floods the inbox. An event is recorded only after
  its email went out, so a failed send is retried next hour. Entries are forgotten 30 days after their
  deadline. To start over (a fresh welcome email), delete that branch.
- **A platform that cannot be read for 24 hours** gets one email saying so, and another when it is
  back. Shorter failures only show as warnings in the Actions run.
- **On a pull request** that touches the watcher the workflow runs the hackathon tests and a dry run
  from GitHub's network, printing the email it would send. Locally:
  `python3 tools/hackathon_watch.py --state .tmp/hackathon_watch/seen.json --dry-run`.
- Not watched: news articles about hackathons. They carry no reliable deadline and would mail rahul
  for every winners' story; they reach the PDF through the opportunity feeds instead.

---

## Troubleshooting
- Gmail OAuth failed → the token refreshes itself; only if that fails, delete `token.json` and rerun
  for a browser prompt
- A source returns 0 articles → it is on the `none from:` line of `.tmp/rss_scrape.log`; fix or remove
  its row in `tools/feed_sources.py` (a source marked `# live` posts less than daily, so leave it)
- `analyzed_content.json` missing → curation (step 2) has not run
- `?` in the PDF where a symbol should be → the character is outside latin-1; add it to
  `sanitize_text()` and `tools/tests/test_sanitize_text.py`
- Summary looks cut off → the renderer no longer shortens summaries at all (since 2026-10-02); a cut
  summary is in the JSON itself. Do not reintroduce a clip or character slicing (`summary[:250]`).
  `test_summary_length.py` guards it
- Title cut mid-word → titles go through `_fit_title()`, which measures width and cuts between words;
  cases in `tools/tests/test_fit_title.py`
- No URL under a story → by design since 2026-10-02: the title is the link, and the line it took
  went to the page limit
- PDF over 15 pages → `verify_edition.py` stops the run; `write_analyzed()` already printed the count
  and the stories to drop (`to fit, drop:`). Drop stories; never shorten an explanation or edit the
  layout to squeeze
- Tests "collect nothing" → they are plain scripts, **not** pytest. `verify_edition.py` runs them;
  `python3 -m pytest tools/tests/` finds nothing because there are no `test_*` functions

## Adding Sources
Add a row to `RSS` in `tools/feed_sources.py`: `(name, url, category, flags)`. The category is the
digest group, and `news_digest.CATEGORY_ORDER` names the section each group feeds. Flags, space
separated: `ai` keeps only entries that mention AI (for general-interest feeds; English only, so a
non-English feed goes unfiltered with an AI search query instead), `musk` keeps only Musk on AI or
autonomy, `browser` sends the browser User-Agent to sites that refuse the bot one, `top` keeps only
the feed's first 20 entries (the regional Google News editions return 100). A
non-RSS source goes in `EXTRA` with a reader in `scrape_rss_feeds.EXTRA_READERS`; keep its parsing in a
pure function and test it offline. **Keyless only:** a source that needs an API key is skipped, even
when the key sits in `.env` (X API, YouTube Data API, NewsAPI). Every source tested and rejected is
listed at the end of `feed_sources.py`; check there before probing one again. `test_sources.py` checks
names, https, the keyless rule and that every section is fed.

---

## Lessons Learned

### Still live — these change what you do
- **2026-10-03: summaries are full explanations; the edition drops stories to fit.** Rahul found the
  400–800 character summaries too thin to understand without looking elsewhere, and kept the
  15-page limit. Summaries are now at least 1,000 characters with no ceiling, written to the five
  parts of the Plain-Language News Rule; sections carry 2–4 stories. Long stories run on overleaf
  instead of moving whole, which reclaimed the blank foot of most pages. Do not go back to trimming
  summaries when an edition runs long: drop a story. Rendering long summaries is slow (fpdf2's line
  breaking costs about 2 seconds per pass for a full edition), so `fit_plan()` bisects its fixed drop
  order instead of re-rendering after every drop; the drop-per-render version took five minutes on
  the test suite's 128-story edition.
- **2026-10-03: the source net is 390 keyless sources.** Probed ~300 candidates; the rejected ones,
  with the reason, are listed at the end of `feed_sources.py` (every github.com `releases.atom` feed
  answers 403 from the cloud; Bluesky search needs a login but profile RSS works; Mastodon hashtag
  feeds are noise). Reddit RSS ends on 13 November 2026, which takes r/LocalLLaMA and the four new
  Reddit rows in the forums group dark together.
- **2026-10-01: Reddit ends RSS on 13 November 2026 (public API in March 2027).** r/LocalLLaMA reaches
  the scrape as an RSS feed and is the open-model section's highest-yield source, so that feed goes
  dark on 13 Nov. A replacement source has to be found and added to `FEEDS` before then, or the
  open-model section will run on the Google News proxies alone.
- **2026-10-01: check the byline before trusting a niche outlet.** Two Forkast pieces (Anthropic's
  "provable-inference deadline", a token-price index) were credited to an AI persona — the author
  blurb ends "Minds are persistent AI beings… Awaken one on Ethoswarm." Their dates and figures
  could not be checked anywhere else, so both were rejected. The tell is in the last lines of the
  `fetch_articles.py` excerpt, so read to the end of a surprising story before drafting it.
- **2026-09-30: an r/LocalLLaMA link post (title ending `\ Anthropic`, body "submitted by…") has no
  text, but one WebSearch of the title finds the source page.** Then `S(idx, ..., title=, url=, source=,
  published_at=)` points the story at the original. `published_at` accepts an override, so the curl
  timestamp trick (2026-09-28, below) dates it exactly. That is how Anthropic's GLM-5.3 cyber analysis led the open-model
  section.
- **2026-09-30: a brand name followed by another word cannot take a bracket gloss.** In `WEH Ventures`
  the token is followed by "Ventures", so a gloss after the full name does nothing. Put the bare token
  first: `WEH (formally WEH Ventures, an Indian venture capital firm)`. Write stylised names in normal
  case (`IIMK Live`, `Deep Leap`), and use "guest replies" rather than `RSVPs`.
- **2026-09-29: an 80-index `fetch_articles.py` batch overflows the tool output, and `| tail` drops
  the first half.** Redirect it to a scratch file and read that instead. If output is lost anyway,
  re-run the missing indices with `--chars N`: everything is cached, so the second call is instant.
  When a page has no `article:published_time`, grepping it for a bare ISO timestamp
  (`2026-09-28T17:58:34Z`) dated the Anthropic policy post.
- **2026-09-28: when WebFetch reports a date with no time, curl the page for its machine timestamp.**
  `curl -sL -A "Mozilla/5.0" URL | grep -oE 'article:published_time" content="[^"]+"|"datePublished":"[^"]+"'`
  gives the full ISO timestamp for `O(..., published_at=...)`, so the 24h gate measures it exactly. A
  date on its own is not enough. That is how the Musk section got its second story (Aroged). Writing
  unit and product names out in full while the builder is open avoids a second verify round: `16-gigabyte`
  rather than `16 GB`, `RTX Pro` rather than `RTX PRO`, and `Flux` rather than `FLUX`.
- **2026-09-25: `too_few_sentences` counts what the splitter sees, not what you wrote.** A sentence
  ending on an abbreviation ("picked up by 24/7 Wall St.") never closes, so it merges with the next;
  a partner list joined by semicolons is one sentence. Two summaries read as 3 sentences for these
  reasons alone. Rephrase so no sentence ends on `St.`/`Inc.`, and split semicolon lists into sentences.
- **2026-09-25: programme back-fill — `hub.causo.ai/deadlines` via WebFetch, then the organiser page.**
  One fetch listed ~25 programmes with sourced deadlines in the next two months; three survived the
  organiser check (a16z speedrun, Techstars AI Health Baltimore, ERA). `speedrun.a16z.com` is
  client-rendered, so `find_opportunities.py check` returns nothing — WebFetch reads it.
- **2026-09-25: when the top of a section hits day four together, rest them together.** Amazon,
  Nebius and Google Cloud AI Builder Cup had all printed 09-22 to 09-24; resting all three and
  returning the two items displaced on 09-24 (Since AI, Build With AI) broke the repeat without
  hunting for new events. Keep one item whose own milestone is close (ARC Prize, 30 Sep). A VR contest
  tagged "Machine Learning/AI" on Devpost (Meta VR Start, $1M cash) is not an AI hackathon — AI was
  optional coding tooling.
- **2026-09-24: a gloss in brackets straight after the token is the form that always passes.** Brand
  names in capitals have no spelled-out form to match (`DNEG`, `ING`, `ASB`, `EDEN`), so write
  `DNEG (a visual-effects studio)`; the same works for `DNA (genetic material)`. `AT&T` trips the
  check on `AT` — include "American Telephone and Telegraph". Writing these in while the builder is
  open made the first verify come back with one warning instead of a second round.
- **2026-09-24: carry opportunities forward from yesterday's backup, don't retype them.** A
  `carry(title, **updates)` helper in the builder loads each verified entry from
  `analyzed_content_<yesterday>.bak.json` and changes only what moved (days-to-close, registrant
  counts). Eleven entries cost about ten lines.
- **2026-09-22: a Devpost headline prize can be ~0.03% cash.** ForgeHacks Online 2026 leads the
  Devpost list at **$330,787** and pays **$100 cash** at first place — the rest is sponsor credits,
  memberships and gift cards, and its own prize page says so ("Total value includes non-cash items.
  Cash portion is $100"). It is also students-only. The `/rules` check is not a formality on the
  biggest number in `.tmp/devpost.txt`; it is most needed there. Same run: the **AWS CDS Agentic AI
  Partner Hackathon** ($40,000, 1st = $18,000 cash) reads eligible from the Devpost panel
  ("Professionals/Post grads only") but its rules restrict entry to people employed by an
  organisation registered with the **AWS Partner Network**, entering with a corporate email on that
  organisation's domain. **Neither restriction is visible without `find_opportunities.py check`** —
  the panel and the prize badge both read clean.
- **2026-09-22: when nothing fresh survives, a recently-displaced item is the fresh entry.** Every
  new hackathon candidate failed (two above, four proxy links would not decode), which would have
  left section 1 a straight four-day repeat. OpenCV AI Competition — dropped on 09-21 only to make
  room, still open, last *printed* 09-16 — rechecked clean and filled the slot. Re-checking the
  rejection log for items rejected on **displacement** rather than on eligibility is cheaper than
  hunting a new one, and it breaks the repeat.
- **2026-09-18: the acronym check could not read the way English writes a name.** It looked for
  initials of *strictly consecutive* words, so `SAE` → "Society **of** Automotive Engineers" and
  `METR` → "Model Evaluation **and** Threat Research" both read as unexplained, and five correctly
  glossed terms were flagged in one edition. It now skips connector words and also accepts an
  appositive gloss (`UNICEF, the United Nations Children's Fund`), which is the form an acronym that
  skips words in its own name has to use. Two cases guard the loosening: a bare acronym with an
  unrelated capitalised phrase nearby must still fire.
- **2026-09-18: `test_check_quality.py` was a time bomb.** Its fixtures passed a fixed `today=` but
  let `now` default to the real clock, so the freshness gate aged a "clean edition" case into a
  `stale_story` ERROR the day after it was written, and `prep_run.py` opened the run with a test
  failure that had nothing to do with the run. Every call now pins `now=NOW`. **Any new case that
  touches dates pins both**, or it breaks tomorrow.
- **2026-09-17: The pipeline was 110 turns, and orientation was most of it.** Turns 4–38 went on
  reading this workflow in chunks, re-reading tool docstrings and polling a detached scraper; turns
  76–110 went on running checks one command per turn at 220–244k context. Neither needed a model.
  `prep_run.py` and `verify_edition.py` now do both, in ~25s total. **Keep them collapsed** — if a new
  check is needed, add it to the tool rather than to the run.
- **2026-09-16: The 2026-09-15 edition was curated but never published, and nothing caught it.**
  The builder raised `KeyError` on a Google News URL, so it never reached `write_analyzed()`,
  `analyzed_content.json` still held the previous day's edition, and the PDF regenerated it silently.
  The backup now happens the moment the PDF verifies.
- **2026-09-16: Devpost's "cash" column still needs the rules page.** Three of the four
  highest-prize events listed cash that the `/rules` page contradicted.
- **2026-09-16: The rebuilt tooling cut the run from ~70 web searches to zero.** Everything the
  curation step reads is pre-cached by `prep_run.py`.
- **2026-09-14: The scraper stores only ~100 characters for image-led feeds**, so a digest line can
  look thin when the article is not. `fetch_articles.py` flags these `THIN` — fetch before judging.
- **2026-09-13: Copying the `best_for` table forward copies its "New today:" labels too.** Use
  `carry_forward_best_for()`, which strips them.
- **2026-09-13: Sunday's feed is thin** (~262 unique articles, heavy proxy duplication). Expect to
  run sections at 3 stories rather than 6, not to pad.
- **2026-09-11: Proxy feeds resurface old events as today's news.** A date in the feed is when the
  proxy saw it, not when it happened.
- **2026-09-21: publishers that 403/405 `fetch_articles.py`, leaving headline-only proxy items.**
  `easternherald.com` and `wionews.com` return HTTP 403, `arstechnica.com` returns 405. When a
  Google News proxy item's only outlet is one of these, the digest line is the *entire* text — there
  is nothing to ground a summary in, so the story is undraftable rather than merely thin. Four
  stories were lost this way in one run (Plugin4Shell, Naive AI's $400M, StepFun Step 5, the Ars
  Technica supply-chain mole), and grepping `rss_articles.json` found no alternate outlet for any of
  them. Check for a second outlet *before* building a section around one of these.
- **2026-09-21: r/LocalLLaMA fetches come back `THIN` (6 chars, "Reddit"), but the scrape has the
  full post.** `reddit.com` blocks the fetcher, yet `rss_articles.json` carries the whole selftext
  from the feed. Read the entry out of the scrape instead of spending a fetch on it — the open-model
  section is mostly Reddit and nearly got dropped on a misread of those `THIN` flags.
- **2026-09-21: Monday's Musk/xAI feed is structurally thin, like Sunday's overall.** The "Elon Musk
  on X" proxy returned three items, two of them bodyless X posts ("Cybertruck as Heavy Cav",
  "Grok @Bot"). The section shipped at 2 stories. `write_analyzed()` prints a story-count warning and
  `check_quality` has no section-count ERROR, so a short section does **not** block the send — run it
  short rather than padding, and never reuse another section's story to fill one (that fires
  `duplicate_across_sections`, which *is* an ERROR).
- **2026-09-21: `ycombinator.com/apply` read-times-out for `find_opportunities.py` check.** Not a
  404 and not a closure — the page simply does not answer in time. Carry the deadline verified on the
  last run that reached it and say so in the summary, rather than dropping a live opportunity.
- **Sites WebFetch cannot read:** `reddit.com`, `theverge.com`, `economictimes.indiatimes.com`,
  `wired.com`, `aicollective.com` (client-side render). Use the feed text or another outlet.
- **Write tool on existing builder scripts** must `Read` before it overwrites. Simpler to write a
  fresh dated builder each day.
- **Don't use Monitor to wait on scrapers** — they write no status files. `prep_run.py` runs them to
  completion instead, which is why nothing needs polling any more.

### Fixed and now guarded by tests — do not re-litigate
| What broke | Where the guard lives |
|---|---|
| Rupee sign and invisible characters printing as `?` | `test_sanitize_text.py`, stray-`?` check |
| Story titles cut mid-word | `test_fit_title.py` |
| Summaries truncated mid-sentence, then clipped at 1,200 characters | `test_summary_length.py` (no clip at all), unfinished-summary check |
| Dates missing from every story in the PDF (2026-09-17) | `test_story_dates.py`, `write_analyzed()` |
| Empty sections spending a page and a contents slot | `generate_pdf.py` skips them |
| A 17-page edition too long to read (2026-10-02) | `test_page_limit.py`, `PAGE_LIMIT`, `page_problem()` |
| Five-line summaries too thin to understand (2026-10-03) | `short_summary` ERROR, `SUMMARY_MIN`, `test_summary_length.py`, `test_check_quality.py` |
| Whole blocks moving overleaf and leaving the foot of the page blank | `_lines_before_break()`, `test_page_limit.py` |
| Blocked publishers (Reuters, NYT, paywalls) leaving a story headline-only | `read_elsewhere()`, `alternates`, `test_wider_sources.py` |
| Opportunity gate matching ordinary English ("models challenge…") | `test_opportunity_gate.py` |
| Email body hardcoded and drifting from the edition | `test_email_body.py` |
| Whole-title PDF comparison flagging 8 good stories | `missing_titles()`, `test_verify_edition.py` |
| News shipping older than 24h because the window was measured at scrape, not send (2026-09-17) | `test_freshness_gate.py`, `stale_story` |
| Acronym check firing on correctly-glossed terms ("Society **of** Automotive Engineers") | `_unexplained_acronyms()`, `test_check_quality.py` |
| Quality-test fixtures ageing into a `stale_story` failure overnight | pinned `now=NOW`, `test_check_quality.py` |
| Acronym check flagging filenames (`AGENTS.md`, `CLAUDE.md`) and the "video memory, or VRAM," gloss | `ACRONYM_RE` lookahead + `_PRE_GLOSS_RE`, `test_check_quality.py` |
| Accented letters outside latin-1 printing as `?` ("Anadolu Ajans?", 2026-09-24) | `_fold_to_latin1()` in `sanitize_text()`, `test_sanitize_text.py` |
| Emoji in post and video titles printing as `?` and blocking the send | `_SYMBOL_CATEGORIES` in `sanitize_text()`, `test_sanitize_text.py` |
| A summary ending `.”` (curly quote) flagged as truncated | `_is_truncated()`, `test_verify_edition.py` |
| `write_analyzed()` flagging valid quantum stories as stale against a flat 24h, though the send gate allows 7 days (2026-10-01) | `stale_hours_for(key)` in `builder_helpers.py`, `test_freshness_gate.py` |
| A hackathon closing in under 7 days, or with only a registration deadline, reaching the PDF (2026-10-03) | `build_time_problem()` in `check_quality.py`, `test_build_window.py` |
| A platform's listing changing shape and its block going quietly empty | fixtures per reader, `test_hackathon_platforms.py` |
| The alert email re-sending a hackathon, or flooding on the first run | `test_hackathon_watch.py` |
| A smaller prize printed above a bigger one in AI Hackathons, or "$100k in credits" outranking cash (2026-10-03) | `prize_usd()` / `by_prize()` in `hackathon_sources.py`, `test_hackathon_prizes.py` |

### History
- **2026-10-03 (later):** AI Hackathons prints biggest prize first, enforced when the PDF is drawn;
  the candidate blocks in `hackathons.txt` and Devpost's newest list are in prize order too.
- **2026-10-03:** On rahul's word that the five-line summaries were too thin ("a clear understanding,
  in layman's terms ... no matter how long it takes in lines") and his choice to keep 15 pages:
  summaries are full explanations of at least 1,000 characters with no ceiling, in five parts
  (what happened, who and what everything is, why, how it works, what changes next), in paragraphs
  when long; sections carry 2–4 stories; long stories run on overleaf; the builder prints the
  stories to drop when the edition runs over; `check_quality` blocks a summary under 1,000
  characters and flags sentences over 45 words. On "search everywhere on the internet" without
  APIs: 172 new keyless sources (218 → 390), including Google News in 14 country editions and 17
  languages, wire services, mainstream, trade, security and science press, regulators, podcasts,
  Reddit and Bluesky; feeds refused with 403/429/503 are retried with the browser User-Agent;
  `fetch_articles.py` prints 5,000 characters and reads a blocked story from another outlet. Tests
  481 → 521 in 21 files.
- **2026-10-03:** Hackathons: the 7-day build rule (submission deadline 7+ days away, registration
  deadlines never count) replaces the near-deadline rule for section 1 and blocks the send. The
  hackathon platforms moved to one keyless registry, `tools/hackathon_sources.py`, and grew from four
  to nine: mlcontests.com (which brings Kaggle, AIcrowd, DrivenData, Zindi, CodaLab and Codabench
  without Kaggle's keyed API), HackerEarth, MLH, TAIKAI and Hackster joined; Devfolio is read from its
  listing page instead of its search API; Unstop is dated by the competition's end, never its
  registration deadline. New hourly alert email from GitHub Actions (see **Hackathon Alerts**).
- **2026-10-02:** Built the approved 16-section restructure (`handoff/`). Three new sections (OpenAI,
  Google AI, xAI & Grok); the Musk section is now "Elon Musk on AI", his own point of view; all
  sixteen in Rahul's order. Summaries are printed whole: the 1,200-character clip and the 1,150
  ceiling are gone. Sources moved to a registry, `tools/feed_sources.py`: 214 feeds (32 kept, 182 new,
  ZDNet AI and xAI Blog dropped) and 4 non-RSS readers, every one keyless. The scraper filters
  general-interest feeds to AI, routes company headlines to their groups and fetches hosts in
  parallel. The digest follows the sections and caps each group; its real size is measured on the
  first full scrape. New `find_opportunities.py platforms` (lablab.ai, Devpost newest, Devfolio,
  Unstop) and X posts read in full. Tests 192 → 332 in 17 files.
  Same evening, on Rahul's word that the PDF was too long to read: 15 pages at most ("make it max 15
  pages", after a 5–6 page version he withdrew). 3–5 stories a section, summaries of 400–800
  characters (the morning's "no upper limit" is withdrawn), a masthead and linked contents list in
  place of the cover page and its chart, sections flowing on instead of a page each, story URLs behind
  the titles. The builder prints the page count and the send blocks above 15. A review of the
  restructure fixed the scraper's de-duplication (one Google News link found by two searches now keeps
  the more specific group instead of the first search's; Hugging Face models are never merged into
  each other; a stale opportunity copy no longer stands in for today's news) and the X post reader
  (only links on X itself, deleted posts count as failed, failures are retried rather than cached).
  The prep brief names a hackathon platform that went unread. Emoji in X and YouTube titles are
  dropped instead of printing as `?`, and a summary ending on a curly closing quote no longer reads
  as cut off. Tests 332 → 378 in 18 files.
- **2026-10-01:** Thursday, quantum in. Shipped 63 stories in 13 sections, 0 errors and 0 warnings on
  the first verify (acronyms glossed while the builder was open), oldest story 21.3h on the 24h rule
  and 138h on the 7-day rule; sent 00:22 UTC, 19 minutes after the scrape. Fixed `write_analyzed()`,
  which measured quantum against 24h at build time (tests 190 → 192). Musk ran at 2 stories: the
  White House accord (Musk signed it, then called it "grading each other's homework") and his Delta
  sandbox post. Both tables carried unchanged; Gemini 4 Argon was kept out of the closed table because
  only Fairwind cyber partners can use it. Rested ARC Prize, OpenCV, Hack Apertus, EF Bangalore,
  Antler and Techstars London, and brought back Amazon, Nebius, Google Cup, Digital Science and YC.
  New: Qloo Agentic Hackathon ($25k cash, global, closes 30 Oct).
- **2026-09-30:** Wednesday, quantum out. Shipped 62 stories in 12 sections, 0 errors, 0 warnings after
  one fix round (3 acronyms: `WEH`, `RSVP`, the stylised `IIMK LIVE`/`DEEP LEAP`), oldest story 21.7h.
  Revised the closed-model table's "Balanced cost" row to GPT-6.1 Sol (same $2/$10 price, vendor
  benchmarks only; `as_of` 2026-09-30); open-model table carried unchanged. Rested Amazon, Nebius, Google
  Cup, Digital Science and YC (printed 09-28 and 09-29); kept ARC Prize (milestone that day) and EF
  Bangalore (closes 5 Oct). New: GitLab's Life After Code ($45k cash, India not excluded). Rejected
  Galuxium Nexus V2: Devpost panel says students only, while its rules text claims to override that.
- **2026-09-29:** Tuesday, quantum out. Shipped 59 stories in 12 sections, 0 errors, 0 warnings after
  one fix round (1 acronym: the satellite name `MOI-1A`), oldest story 20.5h. Both tables carried
  forward unchanged. Rested five opportunities that would have printed a third straight edition (Since
  AI, YouCam, a16z, Techstars Baltimore, ERA) and brought back four rested ones. All four new
  candidates failed: three Devpost events are student-only, and the AIxBio fellowship shows as closed
  on ERA's own site even though an aggregator still lists a 19 Oct deadline.
- **2026-09-28:** Monday, quantum out. Shipped 49 stories in 12 sections, 0 errors, 0 warnings after
  one fix round (4 acronyms: `PRO`, `FLUX`, `SWE`, `GB`), oldest story 16.0h. India ran at 1 story
  and Musk at 2: nothing else AI-related from India fell inside 24h (Lightspeed 09-24, Saaras V4 09-25,
  Google-Flipkart 01:30 UTC 09-27 all too old). Both tables carried forward unchanged.
- **2026-09-25:** Friday, quantum out. Shipped 62 stories in 12 sections, 0 errors, 0 warnings after
  one fix round (4 acronyms, 2 sentence-splitter misreads), oldest story 21.9h. Revised the closed-model
  table's Opus 5.5 row on Endor Labs' independent benchmark (`as_of` 2026-09-25); open-model table
  carried unchanged.
- **2026-09-24:** `sanitize_text()` now folds accented letters outside latin-1 to their base letter
  (explicit entries for the ones with no Unicode decomposition: `ı ł đ`), after a Turkish agency's
  Google News suffix printed as "Ajans?". Tests 187 → 190. Rotated two four-day repeats out of
  hackathons (OpenCV back, Hack Apertus new) and added Antler India to programmes. Run shipped
  66 stories in 13 sections (Thursday, quantum in), 0 errors, 0 warnings, oldest story 21.6h.
- **2026-09-22:** taught the acronym check two more forms it was misreading — a filename
  (`AGENTS.md`, `CLAUDE.md`) is not an acronym, and an expansion may come *first*
  ("video memory, or VRAM,"), which the initials test cannot see because it only looks forward.
  Added `COVID` and `CNBC` to `KNOWN_ACRONYMS`. Guarded by three new cases, including one that keeps
  the pre-gloss branch from swallowing a bare acronym ("or PQR support," has no comma after the
  token, so it still fires). Tests went 156 → 162. Run shipped 57 stories in 11 sections,
  0 errors, 0 warnings, oldest story 20.9h.
- **2026-09-21:** documented the publisher blocks (Eastern Herald, WION 403; Ars Technica 405) that
  make a headline-only proxy item undraftable, the r/LocalLLaMA `THIN` flag that hides full feed
  text, and the Monday Musk-feed shortfall. Run shipped 51 stories in 11 sections, 0 errors, one
  unexpandable acronym (AMI Labs). Nine acronym warnings came from a single pass of missing
  expansions (ARC, CBS, IQ, SEMI, RISC, EY, RGBA, NCCL, CUDA) — expanding on first mention while
  the builder is still open is cheaper than a second verify round.
- **2026-09-18:** loosened the acronym check to match how names are actually written and pinned the
  quality-test clock, after the run opened on a phantom test failure and closed on 16 warnings of
  which 11 were false.
- **2026-09-17:** made the 24-hour rule hard and measured it at **send** rather than at scrape,
  after 34 of 44 news stories arrived over 24h old; reserved a 2h build allowance so the scrape
  window (22h) leaves room for the run to finish inside the rule. Quantum keeps its 7-day rule as
  the single news exception, now enforced rather than merely scraped for.
- **2026-09-12:** split the combined opportunity section into two (hackathons vs grants) after three
  days of the same four items filling one section.
- **2026-09-07:** added the Open Models & Open Weights section; widened the opportunity window to 30
  days after finding the section starved, not mis-curated.
- **2026-09-03:** cut 17 sections to 10; dropped YouTube scraping (`scrape_youtube_trending.py` is no
  longer in the pipeline); rewrote summaries as plain news explanations; fixed the dead Anthropic
  feed (`anthropic.com/rss.xml` has 404'd for months).

---

## Known Feed Issues
- **r/LocalLLaMA RSS stops on 13 November 2026**: Reddit is ending RSS support, announced 2026-09-30
  (TechCrunch). Replace this source before that date (see Lessons, 2026-10-01).
- **X has no keyless feed.** Coverage is the posts Google News has indexed (`site:x.com/<handle>`
  searches), which was accepted on 2026-10-02. Profile timelines answer 429, Nitter mirrors and
  RSSHub are dead, `@xai` has posted nothing since May 2026 and `@grok` is automatic replies, so
  neither is added. One post can still be read in full once found (see Step 2).
- **Bing News rows** need the browser User-Agent and wrap every link in a tracking URL, which the
  scraper unwraps. The outlet's name is read from `<News:Source>` (`news_source`); that field had not
  been seen on a live feed when it was written, so if Bing stories print as "via Bing News", check it.
- **r/LocalLLaMA's replacement is in place:** "Hugging Face new models" in `EXTRA` lists models
  created inside the window, ranked by likes this week.
- VentureBeat AI intermittently returns 0 articles.
- **Opportunity/hackathon platforms probed 2026-09-07 and rejected — do not retry:**
  `devpost.com/hackathons.rss` (HTTP 406 to bot *and* browser UA), `mlh.io/seasons/2026/events.rss`
  (200 with zero entries), `hackerearth.com/challenges/feed/`, `indiaai.gov.in/rss`,
  `indiaai.gov.in/feed` (all 404). MLH and HackerEarth are read another way since 2026-10-03 (the
  events page's own JSON and `hackerearth.com/chrome-extension/events/`). Also probed 2026-10-03 and
  left out: hackathon.com (start dates only), Cerebral Valley and lu.ma (in-person San Francisco
  meetups; Luma's API needs a key), Kaggle directly (keyed API; mlcontests.com covers it),
  `dorahacks.io/api/hackathon/` and `api.topcoder.com/v5/challenges` (404). `opportunitydesk.org/feed/` is live but general-purpose — the AI
  hit rate did not justify the noise. Devpost still works **per competition**
  (`opencv26.devpost.com` fetched fine); only the aggregate feed blocks.
- **Open-model feeds probed 2026-09-07 and rejected — do not retry:** `mistral.ai/news/feed.xml`,
  `ai.meta.com/blog/rss/`, `lmstudio.ai/blog/rss.xml` (404); `qwenlm.github.io/blog/index.xml` (200
  but abandoned, newest post 2025-09-22); `papers.takara.ai/api/feed` (200 but ~4 days behind, and
  arXiv AI/ML already covers papers). Vendor open-model blogs move hosts often — re-probe before
  adding one rather than trusting the URL.
