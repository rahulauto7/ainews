# Plan part 1 — sections, summary length, source registry

CURRENT · written Fri 2 Oct 2026 · nothing below is implemented yet · continues in `plan-2.md`, `plan-3.md`.

Do the tasks in order. For each one: write its test first, run it and see it fail for the stated reason,
make the change, then run the whole suite (command in `HANDOFF.md`, Read first #4).

**Test style** — plain scripts, not pytest. Copy the shape of `tools/tests/test_closed_model_table.py`: a
`check(failures, cond, msg)` helper, `cases += n`, print each `FAIL:` line, then `N/N passed` as the LAST
line (`prep_run.case_count` parses it), exit code 1 on failure. Pin `now=` in any case that touches dates.

## Task 1 — sixteen sections, in his order
**Files:** `tools/generate_pdf.py` (`SECTION_CONFIG` line 34, `SECTION_ORDER` line 118),
`tools/prep_run.py` line 104, new `tools/tests/test_sections.py`.

`SECTION_ORDER`, exactly:
```python
SECTION_ORDER = [
    "ai_hackathons",                   # 1  AI Hackathons
    "product_showcase_opportunities",  # 2  AI Grants, Fellowships & Programs
    "ai_self_improvement_rsi",         # 3  AI Self-Improvement (RSI)
    "quantum_ai_research",             # 4  Quantum + AI (Thursdays only)
    "unaddressed_ai_problems",         # 5  Unaddressed AI Problems
    "ai_business_automation",          # 6  AI Automation & Business
    "ai_business_opportunities",       # 7  AI Business Opportunities
    "indian_ai_industry",              # 8  Indian AI Industry
    "global_ai_news",                  # 9  Global AI News
    "openai_news",                     # 10 OpenAI            (new)
    "google_ai_news",                  # 11 Google AI         (new)
    "anthropic_claude_news",           # 12 Anthropic & Claude Code
    "xai_grok_news",                   # 13 xAI & Grok        (new)
    "open_model_landscape",            # 14 Open Models & Open Weights
    "closed_model_landscape",          # 15 Closed Models & Frontier APIs
    "elon_musk_ai_vision",             # 16 Elon Musk on AI
]
```
Add to `SECTION_CONFIG` (every existing key keeps its label, colour and description):
```python
    "openai_news": {
        "label": "OpenAI", "icon": "○", "color": (16, 163, 127),
        "desc": "OpenAI & ChatGPT - models, products, research, deals, people and policy",
    },
    "google_ai_news": {
        "label": "Google AI", "icon": "▲", "color": (66, 133, 244),
        "desc": "Google, Gemini & DeepMind - models, products, research and company moves",
    },
    "xai_grok_news": {
        "label": "xAI & Grok", "icon": "✖", "color": (96, 125, 139),
        "desc": "xAI the company and its Grok models - releases, features, funding, deals and disputes",
    },
```
Change `elon_musk_ai_vision` to label `"Elon Musk on AI"` and description
`"Elon Musk's own point of view on AI - his X posts, interviews, talks and statements, from across the web"`.

`prep_run.py` line 104: replace `{12 if quantum else 11} sections` with
`{len(SECTION_ORDER) - (0 if quantum else 1)} sections`, and fix the docstring's "the 12 section keys".

**`test_sections.py` cases**
1. `SECTION_ORDER` equals the list above. Fails today: 13 keys in the old order.
2. `set(SECTION_ORDER) == set(SECTION_CONFIG)`.
3. For every key, `desc` is non-empty and at most 186 mm wide in Helvetica italic 8
   (`FPDF().get_string_width`). It is drawn with `cell()`, which does not wrap.
4. "musk" is not in the xAI description, and "xai" is not in the Musk description.

Guards that must stay green: `test_closed_model_table.py` (closed renders directly after open, every
section colour distinct, ORDER and CONFIG hold the same keys). The cover's contents list fits 16 rows
(first row y=177, 6 mm each, cut-off at 280), so the cover needs no change. `send_email.py` builds its
body from the JSON and needs no change. `check_quality.SECTION_STALE_HOURS` needs no change: the new
sections fall under the default 24 hours.

## Task 2 — summaries as long as the story needs
**Files:** `tools/generate_pdf.py` lines 249-269, 412, 432-434; `tools/builder_helpers.py` lines 53, 230;
`tools/check_quality.py` lines 17, 316; new `tools/tests/test_summary_length.py`.

- `generate_pdf.py` line 412 becomes `summary = sanitize_text(story.get("summary", ""))`. Delete
  `clip_to_sentence()`; nothing else calls it.
- `generate_pdf.py` lines 432-434: clamp the tint so a block taller than the page is not drawn past it:
  `pdf.rect(10, y, 190, min(block_h - 1, 282 - y), "F")`. `multi_cell` already breaks the text overleaf.
- `builder_helpers.py` line 53: `SUMMARY_MIN = 600` and no `SUMMARY_MAX`. Line 230: `if n < SUMMARY_MIN:`
  (keep the message text as it is).
- `check_quality.py` line 316 detail: `f"{n} sentences; the floor is {MIN_SENTENCES} and there is no upper limit"`.
  Fix the docstring line 17 to say the same.

**`test_summary_length.py` cases** — render with `GlobalAINewsPDF()`, `alias_nb_pages()`,
`set_auto_page_break(auto=True, margin=15)`, `add_page()`, `build_section(pdf, "global_ai_news", [story])`;
read back with `pypdf.PdfReader(io.BytesIO(bytes(pdf.output())))`; compare with whitespace collapsed.
1. A summary of about 3,000 characters ending in a sentinel sentence: the sentinel is on the page.
   Fails today: clipped at 1,200.
2. A summary of about 12,000 characters renders without raising, runs to two or more pages, sentinel present.
3. `write_analyzed()` prints no `summary ... chars` line for the 3,000-character story (fails today) and
   still prints one for a 300-character story. Call it the way `test_freshness_gate.py` lines 170-180 do:
   `builder_helpers._ARTS = []`, a temp `out_file`, stdout captured, stories dated at the real current time.
4. The `too_few_sentences` detail for a three-sentence summary does not contain "4-7".

## Task 3 — source registry: every keyless source, mapped to a section
**Files:** new `tools/feed_sources.py`, `tools/scrape_rss_feeds.py` (lines 38-121, 158-168, 450-476),
new `tools/tests/test_sources.py`.

1. Create `tools/feed_sources.py` holding only data:
   `RSS = [(name, url, category, flags), ...]` and `EXTRA = [(name, category, kind, arg), ...]`.
   - `RSS` = the 32 existing feeds in the table below, plus every row of `handoff/sources.txt`.
     Do not retype URLs; print the rows with this one-off script and paste its output:
     ```python
     for line in open("handoff/sources.txt", encoding="utf-8"):
         if line.strip() and not line.startswith("#"):
             category, name, url, flags, _status = [p.strip() for p in line.split(" | ")]
             print(f"    ({name!r}, {url!r}, {category!r}, {'' if flags == '-' else flags!r}),")
     ```
   - `EXTRA` = the four non-RSS readers listed at the top of `handoff/recipes.md`.
   - Move the probe-history comments from the old `FEEDS` literal, and the rejected list from
     `recipes.md`, into this file's comments. State the keyless rule in its docstring.
2. In `scrape_rss_feeds.py` replace the `FEEDS` literal and the two hand-written sets:
   ```python
   from feed_sources import EXTRA, RSS

   FEEDS = {name: url for name, url, _category, _flags in RSS}
   CATEGORY = {name: category for name, _url, category, _flags in RSS}
   CATEGORY.update({name: category for name, category, _kind, _arg in EXTRA})
   AI_FILTER_SOURCES = {name for name, _u, _c, flags in RSS if "ai" in flags.split()}
   MUSK_FILTER_SOURCES = {name for name, _u, _c, flags in RSS if "musk" in flags.split()}
   BROWSER_UA_SOURCES = {name for name, _u, _c, flags in RSS if "browser" in flags.split()}
   QUANTUM_SOURCES = {name for name, category in CATEGORY.items() if category == "quantum"}
   OPPORTUNITY_SOURCES = {name for name, category in CATEGORY.items() if category == "opportunity"}
   ```
   `_categorize_source(name)` becomes `return CATEGORY.get(name, "general")`. `window_hours_for()` is
   unchanged, so quantum sources keep the 7-day rule and opportunity sources the 30-day lookback.

**The 32 existing feeds: keep each name and URL exactly, set category and flags**
| Category | Feeds (flag in brackets) |
|---|---|
| general | The Verge AI, TechCrunch AI, Ars Technica AI (ai), MIT Technology Review (ai), VentureBeat AI, The Decoder, AI News, Wired AI, The Register AI, Futurism (ai) |
| openai | OpenAI Blog |
| google | Google AI Blog |
| open_model | Hugging Face Blog, Open Models (via Google News), Open Model Benchmarks (via Google News), r/LocalLLaMA, Ollama Blog |
| indian | Inc42 (ai), YourStory (ai), Economic Times Tech (ai) |
| quantum | arXiv Quantum Physics, Quantum + AI (via Google News) |
| ai_research | arXiv AI, arXiv Machine Learning |
| anthropic_claude | Anthropic News (via Google News), Claude Code (via Google News) |
| elon_musk | Elon Musk on X (via Google News) |
| opportunity | AI Hackathons, AI Competitions, AI Programs, AI Applications Open (all "via Google News") |
| showcase | Product Hunt AI |

Remove `ZDNet AI` and `xAI Blog`: both have returned 404 for weeks. The `ai` flag on the three Indian
feeds and on Ars Technica, MIT Technology Review and Futurism is new behaviour: those feeds are not
AI-only, and the filter (Task 4) keeps just their AI stories.

**`test_sources.py` cases for this task** (Task 4 adds more to the same file)
1. Every name in `RSS` and `EXTRA` is unique; every URL starts with `https://`.
2. Keyless rule: no URL contains `key=`, `apikey`, `api_key` or `token=`, and no host is
   `api.twitter.com`, `api.x.com`, `www.googleapis.com` or `newsapi.org`.
3. Every section in `SECTION_ORDER` is fed: using the category-to-section map in `plan-2.md` Task 5, each
   section has at least one category with at least one source.
4. Windows: `window_hours_for("AI Grants (via Google News)") == 720`,
   `window_hours_for("The Quantum Insider") == 166`, `window_hours_for("OpenAI (via Google News)") == 22`.
   All three fail today: the names are unknown, so each falls to the 22-hour default or is absent.
5. `"ZDNet AI"` and `"xAI Blog"` are not in `FEEDS`.

Guard that must stay green: `test_freshness_gate.py` lines 219-248 call `window_hours_for` with
`"The Verge AI"`, `"Quantum + AI (via Google News)"` and `"AI Hackathons (via Google News)"`, so those
three names must not change.
