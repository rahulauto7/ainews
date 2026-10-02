"""Mechanical quality review of analyzed_content.json, in one turn.

Replaces the four adversarial reviewer agents used until 2026-09-17. Those cost
roughly 4M tokens per run - about a quarter of the whole pipeline - because the
main thread polled them at 240k context, and on 2026-09-17 they consumed the
session limit without returning a verdict. Everything they caught reliably was
mechanical, and mechanical checks belong in a script.

ERROR blocks the send. WARN is printed for a glance and does not block, because
a check that fires on good copy gets ignored, and an ignored check is dead.

  ERROR  banned_phrase             the strategy-note framing dropped 2026-09-03
         truncated                 summary stops mid-sentence
         duplicate_across_sections one story printed in two sections
         stale_story               news older than 24h (quantum: 7d), at send
  WARN   unexplained_acronym       an acronym never expanded in its summary
         too_few_sentences         under the four-sentence floor; there is no upper limit
         stale_best_for            a standing model table older than 21 days

Usage:
  python3 tools/check_quality.py                    # .tmp/analyzed_content.json
  python3 tools/check_quality.py --file PATH --json
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import web_text

OPPORTUNITY_KEYS = ("ai_hackathons", "product_showcase_opportunities")
BEST_FOR_STALE_DAYS = 21

# The hard rule: nothing older than this reaches the inbox. Measured at SEND
# time, not at scrape time. The scraper cuts at 24h from `scraped_at`, but the
# 2026-09-17 edition was mailed 15.6 hours after its scrape, so 34 of its 44
# news stories were over 24h old on arrival while every scrape-side check
# still read clean. Only a check that runs against the clock at send can see it.
STALE_HOURS = 24

# Quantum is the one news section with a wider rule: it runs WEEKLY (Thursdays),
# so each issue covers the whole week since the last one and 24h would leave it
# empty every time. Wider, not absent - 7 days is still a limit that blocks.
# Keep these in step with NEWS_RULE_HOURS / QUANTUM_RULE_HOURS in
# scrape_rss_feeds.py; test_freshness_gate.py fails if they drift.
SECTION_STALE_HOURS = {"quantum_ai_research": 24 * 7}


def stale_hours_for(section_key):
    """The freshness limit, in hours, that applies to a section."""
    return SECTION_STALE_HOURS.get(section_key, STALE_HOURS)
MIN_SENTENCES = 4

# Removed on 2026-09-03: summaries had become strategy essays and the news got
# lost. Matched case-insensitively on the summary text.
BANNED = [
    (r"automation angle", "Automation angle"),
    (r"why it matters for you", "Why it matters for you"),
    (r"\bthe opportunity is\b", "The opportunity is"),
    (r"\byou (?:could|should) (?:build|ship|resell)\b", "build-this advice"),
    (r"\bhere'?s what you can build\b", "build-this advice"),
]

# Acronyms a reader of an AI brief already knows, plus the organisation names
# that are household words. Anything else must be expanded in the same summary.
#
# Only ALL-CAPS tokens are considered at all. The first version also matched
# mixed case and spent its warnings on IonQ, NVQLink, LocalLLaMA, OpenTelemetry,
# CompactifAI and PAQMan - product names, not jargon. 69 warnings on a clean
# edition is a list nobody reads, which is worse than no check.
KNOWN_ACRONYMS = {
    # everyday
    "AI", "API", "CEO", "CTO", "CFO", "COO", "US", "USA", "UK", "EU", "UN", "UAE",
    "IT", "PC", "PDF", "URL", "HTML", "CSS", "SQL", "JSON", "XML", "CSV", "HTTP", "HTTPS",
    "GPU", "CPU", "RAM", "SSD", "HDD", "OS", "CLI", "GUI", "SDK", "IDE", "VR", "AR", "3D",
    "LLM", "ML", "GPT", "GLM", "RAG", "OCR", "NLP", "IPO", "VC", "GDP", "USD", "INR", "GBP", "EUR",
    "IST", "PT", "ET", "PST", "EST", "UTC", "BST", "CEST", "GMT", "AM", "PM", "DC",
    "FAQ", "DIY", "OK", "ID", "IP", "HR", "QA", "UI", "UX", "B2B", "B2C", "SMB", "TV", "PR",
    "R&D", "CO2", "EV", "5G", "4G", "USB", "RTX", "TPU", "NPU", "COVID",
    # organisations a general reader recognises unaided
    "NVIDIA", "IBM", "AMD", "AWS", "TSMC", "ASML", "BMW", "HP", "GE", "SAP", "TCS",
    "NASA", "FBI", "CIA", "SEC", "FTC", "FDA", "DOJ", "NHS", "BBC", "CNN", "CNBC", "MIT", "UCLA",
    "IIT", "IIM", "NATO", "WHO", "IMF", "OPEC", "CERN", "DARPA", "RBI", "SEBI", "MeitY",
    "PTI", "ANI", "AFP", "HQ", "JD", "MAGA", "GOP",
}
# The trailing lookahead drops filenames: AGENTS.md and CLAUDE.md are names on
# disk, not terms a reader needs expanded, and both were flagged on 2026-09-22.
ACRONYM_RE = re.compile(r"\b([A-Z]{2,6})s?\b(?!\.[a-z])")
# "Series XV", "Part III" - a numeral, not a term to explain.
ROMAN_RE = re.compile(r"^[IVXLC]+$")

# Abbreviations whose period does not end a sentence. Masked before counting,
# because Python's re rejects a variable-width lookbehind.
ABBREV_RE = re.compile(
    r"\b(?:Inc|Ltd|Corp|Co|Mr|Mrs|Ms|Dr|Prof|St|vs|etc|e\.g|i\.e|U\.S|U\.K|Jr|Sr|No|Fig|Rs)\.",
    re.IGNORECASE)
SENTENCE_END_RE = re.compile(r"[.!?][\"')\]]?(?=\s|$)")


def _sentences(text):
    """Rough sentence count - good enough to spot a two-line summary."""
    masked = ABBREV_RE.sub(lambda m: m.group(0)[:-1] + "\x00", text or "")
    return len(SENTENCE_END_RE.findall(masked))


def _is_truncated(summary):
    """True when the summary does not end on a finished sentence."""
    s = (summary or "").strip()
    if not s:
        return True
    if s.endswith("..") or s.endswith("…"):
        return True
    return not re.search(r"[.!?][\"')\]]?$", s)


# Words an expansion may contain without contributing an initial. "Society of
# Automotive Engineers" is simply how SAE is written in English, and the first
# version of this check required strictly consecutive words, so it fired on five
# correctly-glossed terms in the 2026-09-18 edition. A check that fires on good
# copy gets ignored, and an ignored check is dead.
_CONNECTORS = r"(?:of|for|and|the|in|on|to|at|a|an|de|&)"

# The other way the plain-language rule allows a term to be defined: name it and
# gloss it immediately, "UNICEF, the United Nations Children's Fund". The
# initials test cannot see these, because the acronym skips words in its own name.
_GLOSS_RE = (r"(?:\s*\(|,?\s+(?:short for|stands for|which stands for|meaning|being)\b"
             r"|,\s+(?:the|a|an)\s+[A-Z])")

# The mirror image: the expansion comes first and the acronym is introduced with
# "or" - "video memory, or VRAM, is the memory on a graphics card". The initials
# test cannot see it either, because the expansion sits before the token rather
# than after it. The trailing comma keeps this to the appositive form; a bare
# mention is not written that way.
_PRE_GLOSS_RE = r",\s+or\s+{}s?,"


def _unexplained_acronyms(summary):
    """Acronyms used without being spelled out anywhere in the same summary.

    An acronym counts as explained two ways: its letters appear as the initials
    of nearby words, allowing the connectors real names contain ("Model
    Evaluation and Threat Research"), or it is followed by an explicit gloss
    ("MCP, the standard that..."). Both are how the plain-language rule asks for
    a term to be written; neither lets a bare acronym through.
    """
    out = []
    gap = r"\w*[^\w]+(?:" + _CONNECTORS + r"[^\w]+)*"
    for token in dict.fromkeys(ACRONYM_RE.findall(summary)):
        if token in KNOWN_ACRONYMS or token.rstrip("s") in KNOWN_ACRONYMS:
            continue
        if ROMAN_RE.match(token):
            continue
        letters = [c for c in token if c.isalpha()]
        # Look for an expansion: initials of nearby words, connectors skipped.
        pattern = r"\b" + gap.join(re.escape(c) for c in letters) + r"\w*"
        if re.search(pattern, summary, re.IGNORECASE):
            continue
        # ...or an appositive gloss right after the acronym itself.
        if re.search(re.escape(token) + _GLOSS_RE, summary):
            continue
        # ...or the expansion first, with the acronym introduced by "or".
        if re.search(_PRE_GLOSS_RE.format(re.escape(token)), summary):
            continue
        out.append(token)
    return out


def _published_instant(story):
    """The LATEST instant a story could have been published, or None.

    `published_at` is the full timestamp and is used as-is. Falling back to
    `published_date` means the time of day is unknown, so the end of that day is
    taken: the most generous reading. A date-only story is then flagged only when
    it is stale under every reading of its own date, never on the date alone.
    """
    raw = story.get("published_at")
    if raw:
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    date = story.get("published_date")
    if not date:
        return None
    try:
        day = datetime.strptime(str(date)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return day + timedelta(days=1)


def story_age_hours(story, now=None):
    """Hours between a story's publication and `now`, or None if it carries no date."""
    when = _published_instant(story)
    if when is None:
        return None
    now = now or datetime.now(timezone.utc)
    return (now - when).total_seconds() / 3600.0


def _ages_by_limit(data, now=None):
    """{limit_hours: [age, ...]} across the sections the freshness rule binds.

    Opportunities are skipped: a hackathon announced three weeks ago and still
    open is not the oldest thing in the briefing, it is the point of the section.
    """
    out = {}
    for key, stories in (data.get("sections") or {}).items():
        if key in OPPORTUNITY_KEYS:
            continue
        for s in stories or []:
            age = story_age_hours(s, now)
            if age is not None:
                out.setdefault(stale_hours_for(key), []).append(age)
    return out


def oldest_story_hours(data, now=None):
    """Age of the oldest story under the standard 24h rule, or None.

    Sections with their own rule (quantum) are excluded on purpose: reporting a
    legal 6-day quantum paper as "oldest news story" against the 24h rule reads
    like a breach every Thursday. freshness_lines() reports those separately.
    """
    ages = _ages_by_limit(data, now).get(STALE_HOURS)
    return max(ages) if ages else None


def freshness_lines(data, now=None):
    """[{limit, oldest, stories}] - one entry per freshness rule actually in play.

    Lets the pre-send report state each rule against its own number instead of
    flattening two different promises into one misleading figure.
    """
    lines = [{"limit": limit, "oldest": max(ages), "stories": len(ages)}
             for limit, ages in _ages_by_limit(data, now).items()]
    return sorted(lines, key=lambda l: l["limit"])


def _title_key(title):
    """Comparable form of a title, for spotting the same story twice."""
    words = re.findall(r"[a-z0-9]+", (title or "").lower())
    return frozenset(w for w in words if len(w) > 3)


def check_edition(data, today=None, now=None):
    """Return a list of findings. Empty means the edition is clean.

    Each finding: {severity, code, section, title, detail}.
    """
    today = today or datetime.now().strftime("%Y-%m-%d")
    now = now or datetime.now(timezone.utc)
    findings = []
    sections = data.get("sections", {}) or {}

    def add(severity, code, section, title, detail):
        findings.append({"severity": severity, "code": code, "section": section,
                         "title": title, "detail": detail})

    seen_urls = {}
    seen_titles = []

    for key, stories in sections.items():
        for s in stories or []:
            title = s.get("title", "")
            summary = s.get("summary", "") or ""

            for pattern, label in BANNED:
                if re.search(pattern, summary, re.IGNORECASE):
                    add("ERROR", "banned_phrase", key, title,
                        f"{label!r} was removed on 2026-09-03; summaries explain the news only")
                    break

            if _is_truncated(summary):
                add("ERROR", "truncated", key, title,
                    f"summary ends mid-sentence: ...{summary.strip()[-60:]!r}")

            url = (s.get("url") or "").rstrip("/")
            if url:
                if url in seen_urls and seen_urls[url] != key:
                    add("ERROR", "duplicate_across_sections", key, title,
                        f"same URL already printed in {seen_urls[url]}")
                else:
                    seen_urls.setdefault(url, key)

            tkey = _title_key(title)
            if len(tkey) >= 4:
                for other_key, other_title, other in seen_titles:
                    if other_key != key and len(tkey & other) >= max(4, int(0.7 * len(tkey))):
                        add("WARN", "near_duplicate_across_sections", key, title,
                            f"looks like {other_title!r} in {other_key}")
                        break
                seen_titles.append((key, title, tkey))

            # Opportunities are dated by the deadline they are still open
            # against, not by the day they were announced, so the rule does not
            # apply to them. Cutting them to 24h emptied the section on 2026-09-07.
            if key not in OPPORTUNITY_KEYS:
                age = story_age_hours(s, now)
                limit = stale_hours_for(key)
                if age is not None and age > limit:
                    rule = f"{limit // 24} days" if limit >= 48 else f"{limit} hours"
                    add("ERROR", "stale_story", key, title,
                        f"published {age / 24:.1f} days ago ({age:.0f}h); the rule for "
                        f"{key} is last {rule}, measured at send")

            n = _sentences(summary)
            if n < MIN_SENTENCES:
                add("WARN", "too_few_sentences", key, title,
                    f"{n} sentences; the floor is {MIN_SENTENCES} and there is no upper limit")

            # One finding per story, not per term: a story using four unexplained
            # acronyms is one summary to rewrite, not four lines to read.
            unexplained = _unexplained_acronyms(summary)
            if unexplained:
                add("WARN", "unexplained_acronym", key, title,
                    "never spelled out: " + ", ".join(unexplained))

    # Every standing table, not just the open-model one: the section each block
    # belongs to is its key, so a second table ages independently and the finding
    # says which one did. Hardcoding the open key let the closed table go stale
    # silently the day it was added (2026-09-22).
    for section_key, block in sorted((data.get("section_extras") or {}).items()):
        if not (block and block.get("as_of")):
            continue
        try:
            age = (datetime.strptime(today, "%Y-%m-%d")
                   - datetime.strptime(block["as_of"], "%Y-%m-%d")).days
            if age > BEST_FOR_STALE_DAYS:
                add("WARN", "stale_best_for", section_key, "best_for table",
                    f"as_of {block['as_of']} is {age} days old; re-check the rows against this week's feed")
        except ValueError:
            add("WARN", "stale_best_for", section_key, "best_for table",
                f"unparsable as_of {block['as_of']!r}")

    order = {"ERROR": 0, "WARN": 1}
    findings.sort(key=lambda f: (order[f["severity"]], f["section"], f["code"]))
    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", default=os.path.join(web_text.TMP_DIR, "analyzed_content.json"))
    ap.add_argument("--json", action="store_true", help="machine-readable findings")
    args = ap.parse_args()

    with open(args.file, encoding="utf-8") as f:
        data = json.load(f)

    findings = check_edition(data)
    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        errors = [f for f in findings if f["severity"] == "ERROR"]
        warns = [f for f in findings if f["severity"] == "WARN"]
        for f in findings:
            print(f"  {f['severity']:5s} {f['code']:28s} [{f['section']}] {f['title'][:52]}")
            print(f"        {f['detail']}")
        stories = sum(len(v or []) for v in data.get("sections", {}).values())
        print(f"check_quality: {stories} stories | {len(errors)} error(s), {len(warns)} warning(s)")
        if not findings:
            print("  clean")
    return 1 if any(f["severity"] == "ERROR" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
