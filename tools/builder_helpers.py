"""
Helpers for the daily builder script, .tmp/build_analyzed_<DATE>.py.

A builder imports these instead of redefining them, so the builder holds only
the day's curation. This docstring IS the format: do not read earlier builder
scripts to copy it. (Before 2026-09-15 every run opened yesterday's ~55 KB
builder for its boilerplate, and those ~14k tokens were then re-sent on every
remaining turn of the run.)

    import sys; sys.path.insert(0, "tools")
    from builder_helpers import S, O, carry_forward_best_for, write_analyzed
    # Two standing tables: the open-weight one, and the closed/frontier one whose
    # rows carry `access` (price + where to get it) in place of `licence`.

    SECTIONS = {}
    # Comments record carry-forward and rejection decisions, as before.
    SECTIONS["anthropic_claude_news"] = [
        S(51, '''Plain-language summary ...''', 5, ["anthropic", "policy"]),
    ]
    SECTIONS["ai_hackathons"] = [
        O("Title", '''Summary ...''', "Devpost (Amazon)", "https://...", 5, ["hackathon"],
          opportunity_type="Online hackathon", deadline="23 Oct 2026", apply_url="...",
          prize="$138k cash", eligibility="Global, adults"),
    ]
    best_for = carry_forward_best_for()   # edit rows / as_of only when a row really changed
    closed = carry_forward_best_for(section_key="closed_model_landscape")
    write_analyzed(SECTIONS, best_for=best_for, closed_best_for=closed,
                   rejected=[("EAZO Global Hackathon", "Devpost removed the event")])

S(idx, ...)  a story from .tmp/rss_articles.json by index. Google News proxy items
             are re-pointed at the publisher: URL decoded (cached in
             .tmp/decoded_urls.json), source taken from the " - Publisher" title
             suffix. Override with source=... / url=... / title=... keywords.
O(...)       an opportunity or story not carried by today's feed, verified on the
             organiser's own page.
rejected     lands in analyzed_content.json as curation_log, and news_digest.py
             prints it tomorrow, so a rejected item is not re-investigated.

Size: every summary is a full plain-language explanation of at least 1,000
characters and as long as the story needs (rahul, 2026-10-03), so a section
carries 2-4 stories, usually 3. Separate paragraphs with a blank line inside the
''' quotes; the PDF keeps them. write_analyzed() prints the PDF's page count and,
over 15 pages, the stories to drop to fit: drop stories, never shorten an
explanation.
"""

import glob
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import web_text

OUTPUT_FILE = os.path.join(web_text.TMP_DIR, "analyzed_content.json")
OPPORTUNITY_KEYS = ("ai_hackathons", "product_showcase_opportunities")
# Summaries explain each story fully in plain language, however many lines that
# takes (rahul, 2026-10-03: "I want a clear understanding, in layman's terms ...
# no matter how long it takes in lines"). The 400-800 character range of
# 2026-10-02 printed five-line summaries that sent him elsewhere to understand
# them. So there is a floor and no ceiling: under 1,000 characters (about nine
# lines on the page) a story cannot carry what happened, who everyone is, why it
# happened and how it works. SUMMARY_MAX stays None: nothing caps a summary.
SUMMARY_MIN, SUMMARY_MAX = 1000, None
# The page limit (15, generate_pdf.PAGE_LIMIT) is met by carrying fewer stories,
# never by shortening explanations. Measured with both model tables and stories
# allowed to run on overleaf: three 2,000-character stories a section is 14 pages
# on a weekday and 15 on a Thursday; four 1,500-character ones 14 and 15.
STORIES_PER_SECTION = (2, 4)

_ARTS = None
_DECODED = None


def _articles():
    global _ARTS
    if _ARTS is None:
        _, _ARTS = web_text.load_articles()
    return _ARTS


def _published_date(article):
    """YYYY-MM-DD for a scraped article, from either field the feeds provide.

    Most feeds give both `published_date` and a full `published` timestamp, but a
    few emit only the timestamp, so the date is derived rather than assumed.
    """
    date = article.get("published_date")
    if date:
        return str(date)[:10]
    raw = article.get("published")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return None


def tidy_summary(summary):
    """Whitespace collapsed inside each paragraph, paragraphs kept.

    A blank line separates paragraphs. A long explanation reads better in two or
    three paragraphs than as one block, and the PDF prints the break.
    """
    paras = [" ".join(p.split()) for p in re.split(r"\n\s*\n", summary or "")]
    return "\n\n".join(p for p in paras if p)


def _story(title, summary, source, url, relevance, tags, extra):
    story = {
        "title": title,
        "summary": tidy_summary(summary),
        "source": source,
        "url": url,
        "relevance": relevance,
        "tags": tags,
    }
    story.update({k: v for k, v in extra.items() if v})
    return story


def S(idx, summary, relevance, tags, **extra):
    """Story from scraped article `idx`, with an agent-written summary."""
    global _DECODED
    a = _articles()[idx]
    title = extra.pop("title", a["title"])
    url = extra.pop("url", None)
    source = extra.pop("source", None)
    # The date the story was published, so the PDF can print it under the title.
    # Editions before 2026-09-17 shipped a blank date on every line because this
    # never left the scraped article. An explicit keyword still wins: a Google
    # News proxy item is dated by the publisher page, not by the day Google
    # resurfaced it.
    # An explicit published_at (an X post's own timestamp, read by fetch_articles)
    # dates the story on the page as well.
    if extra.get("published_at") and not extra.get("published_date"):
        extra["published_date"] = str(extra["published_at"])[:10]
    extra.setdefault("published_date", _published_date(a))
    # The full timestamp as well as the date: check_quality's 24h gate measures
    # the age at SEND, and a date alone cannot tell 01:00 from 23:00 - a 22-hour
    # spread, which is most of the window the rule allows.
    if a.get("published"):
        extra.setdefault("published_at", str(a["published"]))
    if web_text.is_google_news(a["url"]):
        if _DECODED is None:
            _DECODED = web_text.load_decoded_cache()
        if url is None:
            known = a["url"] in _DECODED
            url = web_text.decode_google_news(a["url"], _DECODED)
            if not known:
                web_text.save_decoded_cache(_DECODED)
        if source is None:
            m = re.search(r" - ([^-]+)$", a["title"])
            source = m.group(1).strip() if m else a["source"]
    # A Bing News item names its outlet in `publisher`, so the PDF never says "via Bing News".
    source = source or a.get("publisher") or a["source"]
    return _story(title, summary, source, url or a["url"], relevance, tags, extra)


def O(title, summary, source, url, relevance, tags, **extra):
    """Opportunity or story not carried by today's feed, verified on the organiser's page."""
    return _story(title, summary, source, url, relevance, tags, extra)


# ── Prior editions ────────────────────────────────────────────────────────────

def prior_editions(before_date=None, count=3):
    """[(YYYY-MM-DD, analyzed_content dict)] for the latest `count` editions
    strictly before `before_date` (default: the scrape date), newest first.

    Editions are the dated backups taken before each run
    (analyzed_content_<DATE>.bak.json holds the edition published on DATE).
    """
    if before_date is None:
        data, _ = web_text.load_articles()
        before_date = web_text.local_date(data["scraped_at"])
    by_date = {}
    for path in glob.glob(os.path.join(web_text.TMP_DIR, "analyzed_content_*.bak.json")):
        m = re.search(r"analyzed_content_(\d{4}-\d{2}-\d{2})(\.[a-z_]+)?\.bak\.json$", path)
        if not m or m.group(1) >= before_date:
            continue
        # Prefer the plain backup over variants such as .pre_split for the same date.
        if m.group(1) not in by_date or not m.group(2):
            by_date[m.group(1)] = path
    out = []
    for date in sorted(by_date, reverse=True)[:count]:
        try:
            with open(by_date[date], encoding="utf-8") as f:
                out.append((date, json.load(f)))
        except (OSError, ValueError):
            continue
    return out


def carry_forward_best_for(before_date=None, section_key="open_model_landscape"):
    """Yesterday's best_for block for a section, relabelled for carrying forward.

    Rows keep their text, but a "New today:" prefix becomes "Carried forward:"
    (Lessons 2026-09-13), and as_of keeps the date the table last changed.
    `section_key` picks the table: the open-model one by default, or
    "closed_model_landscape" for the frontier-API table beside it.
    """
    for _, edition in prior_editions(before_date):
        block = (edition.get("section_extras") or {}).get(section_key)
        if block and block.get("best_for"):
            block = json.loads(json.dumps(block))
            for row in block["best_for"]:
                row["why"] = re.sub(r"^New today:\s*", "Carried forward: ", row.get("why", ""))
            return block
    return None


# ── Output ────────────────────────────────────────────────────────────────────

def write_analyzed(sections, best_for=None, closed_best_for=None, rejected=None,
                   out_file=OUTPUT_FILE):
    """Write analyzed_content.json and print a compact check of the result.

    `best_for` / `closed_best_for` are the two standing tables - open-weight
    models and closed frontier APIs. Each is written under its own section key, so
    a section renders its own table and neither ages on the other's schedule.

    `rejected` is a list of (name, reason) pairs for opportunities checked and
    turned down today. Prints counts and problems only - not every title.
    """
    import check_quality
    from generate_pdf import SECTION_CONFIG, SECTION_ORDER

    today = datetime.now().strftime("%Y-%m-%d")
    out = {
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "total_items_analyzed": len(_articles()),
        "sections": sections,
        "section_labels": {k: SECTION_CONFIG[k]["label"] for k in SECTION_ORDER},
        "section_extras": {k: v for k, v in (
            ("open_model_landscape", best_for),
            ("closed_model_landscape", closed_best_for),
        ) if v},
    }
    if rejected:
        out["curation_log"] = {"rejected": [
            {"name": name, "reason": reason, "date": today} for name, reason in rejected
        ]}
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    problems = []
    total = 0
    for key in sections:
        if key not in SECTION_CONFIG:
            problems.append(f"unknown section key {key!r}")
    for key in SECTION_ORDER:
        stories = sections.get(key, [])
        total += len(stories)
        if key == "quantum_ai_research" and not stories:
            continue
        lo, hi = STORIES_PER_SECTION
        if not lo <= len(stories) <= hi:
            problems.append(f"{key}: {len(stories)} stories (rule: {lo}-{hi})")
        for s in stories:
            n = len(s["summary"])
            if n < SUMMARY_MIN or (SUMMARY_MAX and n > SUMMARY_MAX):
                rule = f"{SUMMARY_MIN}-{SUMMARY_MAX}" if SUMMARY_MAX else f"at least {SUMMARY_MIN}"
                problems.append(f"{key}: summary {n} chars (rule: {rule}; explain it fully): "
                                f"{s['title'][:60]}")
            if "automation angle" in s["summary"].lower():
                problems.append(f"{key}: 'Automation angle' is banned: {s['title'][:60]}")
            if not s.get("url"):
                problems.append(f"{key}: no url: {s['title'][:60]}")
            # Opportunities are dated by their deadline and carry no publish date.
            if key not in OPPORTUNITY_KEYS and not s.get("published_date"):
                problems.append(f"{key}: no date: {s['title'][:60]}")
            # The freshness rule, reported here so the curator sees a stale pick
            # while the builder is still open, not from a blocked send half an hour
            # later. Each section's own limit, as the send gate uses: a flat 24h
            # flagged valid quantum stories (7-day rule) on 2026-10-01.
            if key not in OPPORTUNITY_KEYS:
                age = check_quality.story_age_hours(s)
                limit = check_quality.stale_hours_for(key)
                if age is not None and age > limit:
                    problems.append(f"{key}: stale, published {age:.0f}h ago "
                                    f"(rule: {limit}h): {s['title'][:60]}")
    # The page count, while the curator can still cut: the send blocks above the
    # limit, and finding out there costs a re-render and a second verify.
    from generate_pdf import PAGE_LIMIT, page_count
    try:
        pages = page_count(out)
    except Exception as exc:  # noqa: BLE001 - report it; the PDF step will fail loudly
        pages = None
        problems.append(f"the PDF did not render: {exc!r}")
    if pages and pages > PAGE_LIMIT:
        drops = fit_plan(out, PAGE_LIMIT)
        problems.append(f"PDF is {pages} pages (limit {PAGE_LIMIT}): drop stories, never shorten "
                        f"an explanation")
        if drops:
            problems.append("to fit, drop: " + "; ".join(
                f"{key} r{s.get('relevance', '?')} {s['title'][:50]!r}" for key, s in drops))

    chars = [len(s["summary"]) for v in sections.values() for s in v]
    counts = " ".join(f"{n}:{len(sections.get(k, []))}" for n, k in enumerate(SECTION_ORDER, 1))
    print(f"Wrote {out_file}: {total} stories, {pages or '?'} pages | per section in render order {counts}")
    if chars:
        print(f"  summaries: shortest {min(chars):,}, average {sum(chars) // len(chars):,}, "
              f"longest {max(chars):,} characters")
    for p in problems:
        print("  !!", p)
    if not problems:
        print("  no problems found")
    return out


def fit_plan(edition, page_limit):
    """[(section_key, story)] to drop so the edition fits `page_limit` pages.

    Explanations are never shortened to fit (rahul, 2026-10-03), so the only
    lever is how many stories run. Drops go in a fixed order: the lowest-relevance
    story from the section carrying the most, one at a time, never taking a
    section below STORIES_PER_SECTION[0] (or its last story). The order does not
    depend on the layout, so the fewest drops that fit are found by bisecting it,
    a handful of renders rather than one per drop (a 128-story edition took
    minutes the slow way). Returns [] when the edition already fits, and every
    allowed drop when even that leaves it over the limit.
    """
    from generate_pdf import SECTION_ORDER, page_count

    if page_count(edition) <= page_limit:
        return []
    sections = edition.get("sections") or {}
    left = {k: list(range(len(sections.get(k) or []))) for k in SECTION_ORDER}
    floor = max(STORIES_PER_SECTION[0], 1)
    order = []
    while True:
        candidates = [k for k in SECTION_ORDER if len(left[k]) > floor]
        if not candidates:
            break
        most = max(len(left[k]) for k in candidates)
        pool = [(k, pos, i) for k in candidates if len(left[k]) == most
                for pos, i in enumerate(left[k])]
        # Lowest relevance first; among equals, the later story in the later section.
        key, pos, i = min(pool, key=lambda t: (sections[t[0]][t[2]].get("relevance", 3),
                                               -SECTION_ORDER.index(t[0]), -t[1]))
        order.append((key, i))
        del left[key][pos]

    def fits(n):
        gone = set(order[:n])
        trial = dict(edition, sections={k: [s for i, s in enumerate(v) if (k, i) not in gone]
                                        for k, v in sections.items()})
        return page_count(trial) <= page_limit

    lo, hi = 1, len(order)
    if order and fits(hi):
        while lo < hi:
            mid = (lo + hi) // 2
            if fits(mid):
                hi = mid
            else:
                lo = mid + 1
    return [(k, sections[k][i]) for k, i in order[:hi]]
