"""
Generate the daily AI news PDF from analyzed content.
Reads .tmp/analyzed_content.json → Outputs .tmp/ai_news_daily_YYYY-MM-DD.pdf

Six pages at most (PAGE_LIMIT). Rahul, 2026-10-02: "make it less pages, like 5-6
pages, so I can cover every section, understand every section, and read every
section." So page 1 opens with a short masthead and a clickable contents list,
and the sections then flow one after another instead of taking a page each.

Features:
- Color-coded section headers with unique colors per section
- Contents list with each section's page, linked to the section
- Relevance star ratings per story
- Story titles link to the source (the URL itself is not printed)
- Alternating row backgrounds
"""

import json
import os
import sys
import unicodedata
from datetime import datetime

from fpdf import FPDF

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(PROJECT_ROOT, ".tmp")
TODAY = datetime.now().strftime("%Y-%m-%d")
OUTPUT_FILE = os.path.join(TMP_DIR, f"ai_news_daily_{TODAY}.pdf")

# The edition's length (rahul, 2026-10-02). verify_edition.py blocks the send
# above it and builder_helpers.write_analyzed() reports the count while the
# curator can still cut, so the limit is set here and nowhere else.
PAGE_LIMIT = 6
# Lowest y a block may reach before it moves overleaf. Auto page break fires at
# 282 (margin 15); the gap keeps a block from being split by it.
PAGE_BOTTOM = 278
# Section bar (7) + gap (1) + description line (4) + gap (2).
SECTION_HEAD_H = 14
# Summary text: 8pt Helvetica on this leading, in a 178mm column.
SUMMARY_LH = 3.7

# ── Section Config ────────────────────────────────────────────────────────────
SECTION_CONFIG = {
    "ai_hackathons": {
        "label": "AI Hackathons",
        "icon": "\u26a1",
        "color": (255, 179, 0),   # Golden yellow - signals prize energy
        "desc": "High-prize AI hackathons and competitions - global, open to professionals and founders",
    },
    "product_showcase_opportunities": {
        "label": "AI Grants, Fellowships & Programs",
        "icon": "\u2709",
        "color": (0, 128, 128),   # Teal
        "desc": "Grants, fellowships, accelerators, incubators & residencies you can apply to - worldwide",
    },
    "quantum_ai_research": {
        "label": "Quantum + AI",
        "icon": "\u269b",
        "color": (26, 188, 156),  # Turquoise
        "desc": "WEEKLY (Thursdays) - quantum computing breakthroughs where AI is genuinely involved; 7-day window",
    },
    "ai_self_improvement_rsi": {
        "label": "AI Self-Improvement (RSI)",
        "icon": "\u221e",
        "color": (142, 68, 173),  # Dark purple
        "desc": "Recursive self-improvement, AGI progress, alignment research",
    },
    "elon_musk_ai_vision": {
        "label": "Elon Musk on AI",
        "icon": "\u2604",
        "color": (50, 50, 50),    # Dark gray
        "desc": "Elon Musk's own point of view on AI - his X posts, interviews, talks and statements, from across the web",
    },
    "indian_ai_industry": {
        "label": "Indian AI Industry",
        "icon": "\u2605",
        "color": (255, 153, 51),  # India saffron
        "desc": "India-specific AI news, policy, startups, government initiatives",
    },
    "anthropic_claude_news": {
        "label": "Anthropic & Claude Code",
        "icon": "\u25C8",
        "color": (204, 121, 67),  # Warm amber
        "desc": "Claude models, Claude Code & the Agent SDK, Anthropic company news & safety research",
    },
    "open_model_landscape": {
        "label": "Open Models & Open Weights",
        "icon": "\u25CE",
        "color": (233, 30, 99),   # Crimson pink
        "desc": "Open-weight releases, licences & benchmarks - and which open model leads at what",
        "table_heading": "BEST OPEN MODEL RIGHT NOW",
    },
    "closed_model_landscape": {
        "label": "Closed Models & Frontier APIs",
        "icon": "\u25C6",
        "color": (63, 81, 181),   # Indigo
        "desc": "Proprietary frontier models - releases, pricing & benchmarks, and which closed model leads at what",
        "table_heading": "BEST CLOSED MODEL RIGHT NOW",
    },
    "ai_business_automation": {
        "label": "AI Automation & Business",
        "icon": "\u2699",
        "color": (52, 152, 219),  # Blue
        "desc": "AI automation news, agentic tooling, and where the market demand is moving",
    },
    "global_ai_news": {
        "label": "Global AI News",
        "icon": "\u2637",
        "color": (41, 128, 185),  # Steel blue
        "desc": "Worldwide AI: US, EU, China, Japan, Korea, Middle East & more",
    },
    "unaddressed_ai_problems": {
        "label": "Unaddressed AI Problems",
        "icon": "\u2753",
        "color": (180, 30, 30),   # Deep red
        "desc": "Real problems in AI that nobody is solving - gaps & unmet needs",
    },
    "ai_business_opportunities": {
        "label": "AI Business Opportunities",
        "icon": "\u2728",
        "color": (46, 204, 113),  # Green
        "desc": "Emerging business opportunities in AI - India & world",
    },
    # One section per top AI company (2026-10-02). Anthropic already had one above.
    "openai_news": {
        "label": "OpenAI",
        "icon": "\u25CB",
        "color": (16, 163, 127),  # OpenAI green
        "desc": "OpenAI & ChatGPT - models, products, research, deals, people and policy",
    },
    "google_ai_news": {
        "label": "Google AI",
        "icon": "\u25B2",
        "color": (66, 133, 244),  # Google blue
        "desc": "Google, Gemini & DeepMind - models, products, research and company moves",
    },
    "xai_grok_news": {
        "label": "xAI & Grok",
        "icon": "\u2716",
        "color": (96, 125, 139),  # Blue grey
        "desc": "xAI the company and its Grok models - releases, features, funding, deals and disputes",
    },
}

# Rendering order: Rahul's list of 2026-10-02, with the four company sections
# (OpenAI, Google AI, Anthropic & Claude Code, xAI & Grok) between Global AI News
# and the two model tables. Changing it is his decision, not a refactor.
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
    "openai_news",                     # 10 OpenAI
    "google_ai_news",                  # 11 Google AI
    "anthropic_claude_news",           # 12 Anthropic & Claude Code
    "xai_grok_news",                   # 13 xAI & Grok
    "open_model_landscape",            # 14 Open Models & Open Weights
    "closed_model_landscape",          # 15 Closed Models & Frontier APIs
    "elon_musk_ai_vision",             # 16 Elon Musk on AI
]


class GlobalAINewsPDF(FPDF):
    """Custom PDF with headers, footers, and styling."""

    def header(self):
        if self.page_no() == 1:
            return  # page 1 carries the masthead
        self.set_fill_color(26, 26, 46)
        self.rect(0, 0, 210, 9, "F")
        self.set_font("Helvetica", "B", 7.5)
        self.set_text_color(200, 200, 200)
        self.set_xy(8, 1.5)
        self.cell(100, 6, "GLOBAL AI NEWS DAILY BRIEFING")
        self.set_xy(150, 1.5)
        self.cell(52, 6, TODAY, align="R")
        self.set_text_color(0, 0, 0)
        self.set_y(12)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}  |  Global AI News  |  {TODAY}", align="C")


def sanitize_text(text):
    """Replace Unicode characters that Helvetica can't render."""
    replacements = {
        "\u2014": "-",   # em-dash
        "\u2013": "-",   # en-dash
        "\u2018": "'",   # left single quote
        "\u2019": "'",   # right single quote
        "\u201c": '"',   # left double quote
        "\u201d": '"',   # right double quote
        "\u2026": "...", # ellipsis
        "\u2022": "-",   # bullet
        "\u00a0": " ",   # non-breaking space
        "\u2011": "-",   # non-breaking hyphen
        # Invisible formatting characters. They carry no width, so "?" is always
        # wrong for them: YourStory titles arrive with a leading word joiner and
        # the 2026-09-16 draft printed "?Government to Match VC Investments...".
        # Reuters copy syndicated through Economic Times is peppered with them.
        "\u200b": "",    # zero-width space
        "\u200c": "",    # zero-width non-joiner
        "\u200d": "",    # zero-width joiner
        "\u2060": "",    # word joiner
        "\ufeff": "",    # zero-width no-break space / BOM
        "\u200e": "",    # left-to-right mark
        "\u200f": "",    # right-to-left mark
        # Currency signs outside latin-1 printed as "?" until 2026-09-13
        # ("from ?50 to ?5-15"). The pound sign is latin-1 and needs no entry.
        "\u20b9": "Rs ",  # rupee sign
        "\u20ac": "EUR ", # euro sign
        "\U0001d54f": "X",  # mathematical double-struck X, used for the X app
        # Letters with no Unicode decomposition, so the fold below cannot reach
        # them. "Anadolu Ajansi" printed as "Ajans?" in the 2026-09-24 draft.
        "ı": "i", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D",
    }
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    # Fold other accented letters outside latin-1 (s-cedilla, z-acute, dotted I)
    # to their base letter rather than "?". Latin-1 letters are left as they are.
    if any(ord(c) > 0xFF for c in text):
        text = "".join(c if ord(c) <= 0xFF else _fold_to_latin1(c) for c in text)
    # Strip any remaining non-latin-1 characters
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _fold_to_latin1(char):
    """Base letter of an accented character, or the character itself if none."""
    base = "".join(c for c in unicodedata.normalize("NFKD", char) if not unicodedata.combining(c))
    return base if base and all(ord(c) <= 0xFF for c in base) else char


def render_stars(relevance):
    """Return star string for relevance score."""
    filled = min(max(int(relevance), 0), 5)
    return "*" * filled + "." * (5 - filled)  # star rating


def _section_renders(section_key, sections_data, section_extras):
    """True if this section will be drawn.

    A section earns its place by having stories, or by carrying a standing reference
    table in `section_extras` (the open-model `best_for` box), which is worth showing
    on its own. Everything else is skipped so empty sections never reach the PDF.
    """
    if sections_data.get(section_key):
        return True
    extras = (section_extras or {}).get(section_key) or {}
    return bool(extras.get("best_for"))


def build_masthead(pdf, sections_data, rendered, links, pages=None):
    """Page 1's top: a title band, then the contents list in two columns.

    Replaced the full cover page (title block, coverage chart, contents) on
    2026-10-02: it took the whole of page 1 out of a six-page budget. Each entry
    links to its section and, once render_edition() has found it, names the page
    the section starts on. Returns the y the first section starts from.
    """
    pdf.set_fill_color(26, 26, 46)
    pdf.rect(0, 0, 210, 26, "F")
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(10, 5)
    pdf.cell(190, 10, "GLOBAL AI NEWS", align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(255, 215, 0)
    pdf.set_xy(10, 15)
    nice_date = datetime.now().strftime("%A, %B %d, %Y")
    pdf.cell(190, 6, f"Daily Intelligence Briefing  |  {nice_date}", align="C")

    total = sum(len(sections_data.get(k) or []) for k in rendered)
    y = 30
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(26, 26, 46)
    pdf.set_xy(12, y)
    pdf.cell(186, 5, f"IN THIS EDITION  -  {len(rendered)} sections, {total} stories")
    y += 6

    # Numbered down the left column, then down the right, so the order reads the
    # same as the pages that follow.
    rows = (len(rendered) + 1) // 2
    pdf.set_font("Helvetica", "", 8)
    for i, key in enumerate(rendered):
        col, row = divmod(i, rows)
        x, ry = 12 + col * 95, y + row * 5
        r, g, b = SECTION_CONFIG[key]["color"]
        pdf.set_fill_color(r, g, b)
        pdf.rect(x, ry + 0.8, 2.5, 3.4, "F")
        count = len(sections_data.get(key) or [])
        label = f"{i + 1}. {SECTION_CONFIG[key]['label']}" + (f"  ({count})" if count else "")
        pdf.set_text_color(50, 50, 50)
        pdf.set_xy(x + 4, ry)
        pdf.cell(76, 5, sanitize_text(label), link=links[key])
        if pages and key in pages:
            pdf.set_text_color(130, 130, 130)
            pdf.cell(10, 5, f"p{pages[key]}", align="R", link=links[key])
    y += rows * 5 + 2

    pdf.set_draw_color(220, 220, 228)
    pdf.set_line_width(0.3)
    pdf.line(12, y, 198, y)
    pdf.set_text_color(0, 0, 0)
    return y + 1


def _story_height(pdf, story):
    """Height a story block takes: title, metadata line, summary, padding.

    Measured before drawing so the background box and the page break both match
    the real rendered height.
    """
    pdf.set_font("Helvetica", "", 8)
    pdf.set_x(14)
    summary_h = pdf.multi_cell(178, SUMMARY_LH, sanitize_text(story.get("summary", "")),
                               dry_run=True, output="HEIGHT")
    return 10.5 + summary_h + 2


def build_section(pdf, section_key, stories, extras=None, link=None):
    """Draw one section where the page currently stands: header, table, stories.

    `extras` is the section's entry from `section_extras` in analyzed_content.json.
    Sections that carry no extras pass None. `link` is the contents entry's
    internal link, pointed here. Returns the page the section's header landed on.

    Sections flow on from the one before; the header moves overleaf only when it
    and the section's first block would not fit under it together, so a header
    is never left alone at the foot of a page.
    """
    config = SECTION_CONFIG[section_key]
    r, g, b = config["color"]
    has_table = bool(extras and extras.get("best_for"))

    y = pdf.get_y()
    if y > 20:
        y += 2  # space after the previous section; none at the top of a page

    if has_table:
        first_h = _best_for_layout(pdf, extras)[2]
    elif stories:
        first_h = _story_height(pdf, stories[0])
    else:
        first_h = 8
    # A block taller than a page starts where it is anyway (see below), so it
    # cannot be the reason to move the header.
    if y + SECTION_HEAD_H + (first_h if first_h <= 260 else 30) > PAGE_BOTTOM:
        pdf.add_page()
        y = pdf.get_y()
    if link is not None:
        pdf.set_link(link, y=y, page=pdf.page_no())
    page = pdf.page_no()

    # Section header bar
    pdf.set_fill_color(r, g, b)
    pdf.rect(10, y, 190, 7, "F")
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(13, y + 0.5)
    pdf.cell(184, 6, config["label"].upper())
    y += 8

    # Section description
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(100, 100, 100)
    pdf.set_xy(12, y)
    pdf.cell(186, 4, sanitize_text(config["desc"]))
    y += 6

    # Standing reference table - the open- and closed-model sections each carry one.
    # Gated on the data rather than the section key, so any section can grow one later.
    if has_table:
        y = build_best_for_box(pdf, y, config["color"], extras,
                               _table_heading(section_key, extras))

    if not stories:
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(150, 150, 150)
        pdf.set_xy(14, y)
        pdf.cell(180, 5, "No stories in this section today.")
        pdf.set_y(y + 6)
        return page

    for idx, story in enumerate(stories):
        title = sanitize_text(story.get("title", "Untitled"))
        summary = sanitize_text(story.get("summary", ""))
        story_url = story.get("url", "")
        meta_line = _fit_meta_line(pdf, _meta_parts(section_key, story), 178)
        block_h = _story_height(pdf, story)

        # Page break if this story will not fit. A block taller than a whole page
        # cannot fit anywhere, so it starts where it is unless the page is nearly
        # full; multi_cell carries the rest of the summary overleaf.
        if y + block_h > PAGE_BOTTOM and (block_h <= 260 or y > 230):
            pdf.add_page()
            y = pdf.get_y()

        # Alternating background, sized to the measured block but never drawn past
        # the bottom of the page.
        if idx % 2 == 0:
            pdf.set_fill_color(245, 247, 250)
            pdf.rect(10, y, 190, min(block_h - 1, 282 - y), "F")

        # Title (a link to the story) + relevance stars
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(25, 75, 200)
        pdf.set_xy(14, y + 1)
        pdf.cell(155, 5, _fit_title(pdf, title, 155), link=story_url)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(r, g, b)
        pdf.cell(25, 5, render_stars(story.get("relevance", 3)), align="R")

        # Source / metadata line
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(120, 120, 120)
        pdf.set_xy(14, y + 6)
        pdf.cell(180, 4, meta_line)

        # Summary - full sentences, no truncation
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(60, 60, 60)
        pdf.set_xy(14, y + 10.5)
        pdf.multi_cell(178, SUMMARY_LH, summary)
        y = pdf.get_y() + 2

    pdf.set_y(y)
    return page


def build_best_for_box(pdf, y, color, extras, heading="BEST MODEL RIGHT NOW"):
    """Draw a standing "which model is best at what" table.

    Entries come from analyzed_content.json, never from code, so the table is
    rewritten each run instead of ageing into a hardcoded lie. The `as_of` date is
    printed in the heading so a stale table is visible rather than silent.

    Returns the y to continue drawing from; returns it unchanged if there is nothing
    to draw.
    """
    entries, row_heights, box_h = _best_for_layout(pdf, extras)
    if not entries:
        return y

    r, g, b = color
    label_w, why_w = BEST_FOR_LABEL_W, BEST_FOR_WHY_W
    why_x, why_lh = BEST_FOR_WHY_X, BEST_FOR_WHY_LH

    if y + box_h > 275:
        pdf.add_page()
        y = pdf.get_y() + 2

    pdf.set_fill_color(250, 250, 252)
    pdf.set_draw_color(r, g, b)
    pdf.set_line_width(0.4)
    pdf.rect(12, y, 186, box_h, "DF")

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(r, g, b)
    pdf.set_xy(16, y + 1.5)
    pdf.cell(178, 5, sanitize_text(heading))

    row_y = y + 8
    for entry, row_h in zip(entries, row_heights):
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(60, 60, 60)
        pdf.set_xy(16, row_y)
        pdf.multi_cell(label_w, 4.6, sanitize_text(entry["use_case"]), align="L")

        pdf.set_text_color(r, g, b)
        pdf.set_xy(50, row_y)
        pdf.cell(why_w, 4.6, sanitize_text(_model_line(entry)))

        why = sanitize_text(entry.get("why", ""))
        if why:
            pdf.set_font("Helvetica", "", 7)
            pdf.set_text_color(110, 110, 110)
            pdf.set_xy(why_x, row_y + 4.6)
            pdf.multi_cell(why_w, why_lh, why)

        row_y += row_h

    pdf.set_text_color(0, 0, 0)
    return y + box_h + 4


BEST_FOR_LABEL_W, BEST_FOR_WHY_W = 34.0, 142.0
BEST_FOR_WHY_X, BEST_FOR_WHY_LH = 52.0, 3.4


def _best_for_layout(pdf, extras):
    """(entries, row heights, box height) for a standing table, without drawing.

    Every row is measured before anything is drawn, the same way the story blocks
    are, so the border ends up matching the content it wraps - and so a section
    header can tell whether the table will fit under it.
    """
    entries = [
        e for e in (extras or {}).get("best_for", [])
        if e.get("use_case") and e.get("model")
    ]
    row_heights = []
    for entry in entries:
        pdf.set_font("Helvetica", "", 7)
        why = sanitize_text(entry.get("why", ""))
        pdf.set_x(BEST_FOR_WHY_X)
        why_h = (
            pdf.multi_cell(BEST_FOR_WHY_W, BEST_FOR_WHY_LH, why, dry_run=True, output="HEIGHT")
            if why else 0
        )
        # The label wraps inside its own column, so a long use_case grows the row
        # rather than running into the model line. Measured in the label's own font.
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_x(16)
        label_h = pdf.multi_cell(BEST_FOR_LABEL_W, 4.6, sanitize_text(entry["use_case"]),
                                 dry_run=True, output="HEIGHT")
        row_heights.append(max(4.6 + why_h, label_h) + 1.4)
    return entries, row_heights, 8 + sum(row_heights) + 3


def _table_heading(section_key, extras):
    """The table's heading, with the as_of date it was last revised.

    Printed rather than kept in code so a table that has stopped being revised is
    visible on the page instead of quietly ageing into a wrong answer.
    """
    heading = SECTION_CONFIG.get(section_key, {}).get("table_heading", "BEST MODEL RIGHT NOW")
    as_of = (extras or {}).get("as_of", "")
    return f"{heading}   (as of {as_of})" if as_of else heading


def _model_line(entry):
    """'Model (maker, licence-or-access)', dropping whichever parts the entry lacks.

    An open model's row carries a `licence`, because "open" ranges from MIT to
    licences forbidding commercial use. A closed model has no licence to quote, so
    its row carries `access` instead - what it costs and where to get it, which is
    the thing the reader equally cannot infer from the model's name.
    """
    terms = entry.get("licence", "") or entry.get("access", "")
    tail = ", ".join(part for part in (entry.get("maker", ""), terms) if part)
    model = entry.get("model", "")
    return f"{model} ({tail})" if tail else model


def _fit_title(pdf, title, max_w):
    """Shorten a story title so it fits its one-line cell, cutting between words.

    Titles used to be sliced with title[:95], which cut mid-word ("- The Ne") and
    still overflowed when the characters were wide. Measures in the current font,
    so call it after set_font().
    """
    if pdf.get_string_width(title) <= max_w:
        return title
    words = title.split(" ")
    while len(words) > 1 and pdf.get_string_width(" ".join(words) + "...") > max_w:
        words.pop()
    label = " ".join(words).rstrip(" -|:,")
    # A single word wider than the cell: fall back to trimming characters.
    while label and pdf.get_string_width(label + "...") > max_w:
        label = label[:-1]
    return label + "..."


def _format_published(story):
    """Human-readable publish date, e.g. 'Sep 2, 2026'.

    Accepts either a plain YYYY-MM-DD in `published_date` or a full ISO timestamp
    in `published`. Returns "" when the story carries no usable date.
    """
    raw = story.get("published_date") or story.get("published") or ""
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return str(raw)
    # %-d is platform-specific; strip the zero manually so it works everywhere.
    return f"{dt.strftime('%b')} {dt.day}, {dt.year}"


def _fit_meta_line(pdf, parts, max_width):
    """Join metadata parts, dropping from the tail until the line fits.

    The metadata line is drawn with cell(), which does not wrap - anything wider
    than the column runs past the right margin. The opportunity section carries up
    to seven fields (source, date, type, deadline, prize, eligibility, apply link),
    which overflows easily, so parts are dropped from the END, where the least
    important ones sit. Source and date are never dropped.
    """
    pdf.set_font("Helvetica", "", 7)
    parts = [sanitize_text(p) for p in parts]

    while len(parts) > 2:
        line = "  |  ".join(parts)
        if pdf.get_string_width(line) <= max_width:
            return line
        parts.pop()

    return "  |  ".join(parts)


def _meta_parts(section_key, story):
    """Build the grey metadata line under a story title."""
    parts = [f"Source: {story.get('source', 'Unknown')}"]

    # The opportunity sections are dated by their deadline, not their announcement,
    # and _fit_meta_line never drops parts[0] or parts[1] - so a publish date here
    # would sit ahead of "Due:" and "Apply:" and push them off the end of the line.
    if section_key not in ("ai_hackathons", "product_showcase_opportunities"):
        published = _format_published(story)
        if published:
            parts.append(published)

    if section_key == "unaddressed_ai_problems":
        if story.get("who_affected"):
            parts.append(f"Affects: {story['who_affected']}")
        if story.get("severity"):
            parts.append(f"[{story['severity'].upper()}]")
    elif section_key in ("product_showcase_opportunities", "ai_hackathons"):
        # Deadline leads: for something you enter, the date you stop being able to
        # is the single most useful fact on the line. Every field is optional -
        # Google News carries articles ABOUT opportunities, so a clean deadline or
        # apply link often is not in the source, and a blank beats an invention.
        # Ordered by what a reader acts on, because _fit_meta_line drops from the
        # tail: the date you stop being able to enter, then how to enter, then
        # what it is worth. Labels are terse for the same reason - every character
        # spent on "Deadline:" is one that pushes the apply link off the line. The
        # type and prize carry no label at all; neither needs one to be read.
        if story.get("opportunity_type"):
            parts.append(story["opportunity_type"])
        if story.get("deadline"):
            parts.append(f"Due: {story['deadline']}")
        if story.get("apply_url"):
            parts.append(f"Apply: {story['apply_url']}")
        if story.get("prize"):
            parts.append(story["prize"])
        if story.get("eligibility"):
            parts.append(f"For: {story['eligibility']}")

    return parts


def render_edition(data):
    """Draw the whole edition and return the FPDF object, not yet saved.

    Drawn twice: the first pass finds the page each section starts on, the second
    prints those pages in the contents list. The list is the same height either
    way, so both passes lay the pages out identically.
    """
    sections_data = data.get("sections") or {}
    section_extras = data.get("section_extras") or {}
    # Sections with nothing to show are skipped entirely. Quantum + AI is absent
    # six days a week by design. A section that carries extras (a model table)
    # still renders with no stories, because the table is the point.
    rendered = [k for k in SECTION_ORDER
                if _section_renders(k, sections_data, section_extras)]
    pages = None
    for _ in range(2):
        pdf = GlobalAINewsPDF()
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        links = {k: pdf.add_link() for k in rendered}
        pdf.set_y(build_masthead(pdf, sections_data, rendered, links, pages))
        pages = {k: build_section(pdf, k, sections_data.get(k, []),
                                  section_extras.get(k), links[k])
                 for k in rendered}
    return pdf


def generate_pdf():
    """Main function: load analyzed content and generate PDF."""
    input_file = os.path.join(TMP_DIR, "analyzed_content.json")

    if not os.path.exists(input_file):
        print("ERROR: analyzed_content.json not found. Run analyze_and_categorize.py first.")
        sys.exit(1)

    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("Generating PDF...")
    pdf = render_edition(data)

    os.makedirs(TMP_DIR, exist_ok=True)
    pdf.output(OUTPUT_FILE)

    file_size = os.path.getsize(OUTPUT_FILE) / 1024
    sections_data = data.get("sections", {})
    total_stories = sum(len(sections_data.get(s, [])) for s in SECTION_ORDER)
    pages = pdf.page_no()
    over = f" - OVER the {PAGE_LIMIT}-page limit" if pages > PAGE_LIMIT else ""

    print(f"\nPDF generated: {OUTPUT_FILE}")
    print(f"  Size: {file_size:.0f} KB")
    print(f"  Pages: {pages}{over}")
    print(f"  Stories: {total_stories}")

    return OUTPUT_FILE


if __name__ == "__main__":
    generate_pdf()
