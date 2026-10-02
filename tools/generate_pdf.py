"""
Generate an attractive daily AI news PDF from analyzed content.
Reads .tmp/analyzed_content.json → Outputs .tmp/ai_news_daily_YYYY-MM-DD.pdf

Features:
- Color-coded section headers with unique colors per section
- Cover page with date, table of contents, and topic distribution chart
- Relevance star ratings per story
- Source attribution and URLs
- Alternating row backgrounds
- Charts via matplotlib
"""

import json
import os
import sys
import unicodedata
import io
from datetime import datetime, timezone

from fpdf import FPDF
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(PROJECT_ROOT, ".tmp")
TODAY = datetime.now().strftime("%Y-%m-%d")
OUTPUT_FILE = os.path.join(TMP_DIR, f"ai_news_daily_{TODAY}.pdf")

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
            return  # Cover page has custom header
        self.set_fill_color(26, 26, 46)
        self.rect(0, 0, 210, 12, "F")
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(200, 200, 200)
        self.set_xy(5, 3)
        self.cell(100, 6, "GLOBAL AI NEWS DAILY BRIEFING", new_x="RIGHT")
        self.set_xy(150, 3)
        self.cell(55, 6, TODAY, align="R")
        self.set_text_color(0, 0, 0)
        self.ln(12)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}  |  Global AI News  |  {TODAY}", align="C")


def generate_topic_chart(sections_data):
    """Generate a bar chart of stories per section. Returns PNG bytes."""
    labels = []
    counts = []
    colors = []

    for section_key in SECTION_ORDER:
        config = SECTION_CONFIG[section_key]
        stories = sections_data.get(section_key, [])
        if stories:
            labels.append(config["label"])
            counts.append(len(stories))
            r, g, b = config["color"]
            colors.append((r / 255, g / 255, b / 255))

    if not labels:
        return None

    fig, ax = plt.subplots(figsize=(7, 3.5))
    bars = ax.barh(range(len(labels)), counts, color=colors, height=0.6)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("Number of Stories", fontsize=8)
    ax.set_title("Today's Coverage Distribution", fontsize=10, fontweight="bold")
    ax.invert_yaxis()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    for bar, count in zip(bars, counts):
        ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                str(count), va="center", fontsize=7, fontweight="bold")

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


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
    """True if this section will produce a page.

    A section earns its page by having stories, or by carrying a standing reference
    table in `section_extras` (the open-model `best_for` box), which is worth showing
    on its own. Everything else is skipped so empty sections never reach the PDF.
    """
    if sections_data.get(section_key):
        return True
    extras = (section_extras or {}).get(section_key) or {}
    return bool(extras.get("best_for"))


def build_cover_page(pdf, sections_data, section_extras=None):
    """Build the cover page with title, date, chart, and table of contents."""
    # Dark header bar
    pdf.set_fill_color(26, 26, 46)
    pdf.rect(0, 0, 210, 70, "F")

    # Title
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(15, 15)
    pdf.cell(180, 15, "GLOBAL AI NEWS", align="C")

    # Subtitle
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(180, 200, 255)
    pdf.set_xy(15, 32)
    pdf.cell(180, 10, "Daily Intelligence Briefing", align="C")

    # Date
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(255, 215, 0)
    pdf.set_xy(15, 48)
    nice_date = datetime.now().strftime("%A, %B %d, %Y")
    pdf.cell(180, 10, nice_date, align="C")

    pdf.set_text_color(0, 0, 0)

    # Topic distribution chart
    chart_buf = generate_topic_chart(sections_data)
    if chart_buf:
        chart_path = os.path.join(TMP_DIR, "topic_chart.png")
        with open(chart_path, "wb") as f:
            f.write(chart_buf.read())
        pdf.image(chart_path, x=15, y=75, w=180)

    # Table of contents
    toc_y = 165
    pdf.set_xy(15, toc_y)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(26, 26, 46)
    pdf.cell(180, 8, "TABLE OF CONTENTS", align="C")
    toc_y += 12

    pdf.set_font("Helvetica", "", 9)
    # Number only the sections that actually render, so the TOC numbering matches the
    # pages that follow it on days a section is absent.
    rendered = [k for k in SECTION_ORDER
                if _section_renders(k, sections_data, section_extras)]
    for i, section_key in enumerate(rendered, 1):
        config = SECTION_CONFIG[section_key]
        stories = sections_data.get(section_key, [])
        count = len(stories)

        r, g, b = config["color"]
        pdf.set_fill_color(r, g, b)
        pdf.rect(20, toc_y, 3, 5, "F")

        pdf.set_text_color(50, 50, 50)
        pdf.set_xy(26, toc_y)
        label_text = f"{i}. {config['label']}"
        if count > 0:
            label_text += f"  ({count} stories)"
        pdf.cell(160, 5, label_text)
        toc_y += 6

        if toc_y > 280:
            break


def build_section(pdf, section_key, stories, extras=None):
    """Build a full section with header, description, and stories.

    `extras` is the section's entry from `section_extras` in analyzed_content.json.
    Sections that carry no extras pass None and render exactly as before.
    """
    config = SECTION_CONFIG[section_key]
    r, g, b = config["color"]

    if pdf.get_y() > 230:
        pdf.add_page()

    y = pdf.get_y() + 5

    # Section header bar
    pdf.set_fill_color(r, g, b)
    pdf.rect(10, y, 190, 12, "F")
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(15, y + 1)
    pdf.cell(180, 10, f"  {config['label'].upper()}")
    y += 14

    # Section description
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.set_xy(12, y)
    pdf.cell(186, 5, sanitize_text(config["desc"]))
    y += 7

    # Thin accent line
    pdf.set_draw_color(r, g, b)
    pdf.set_line_width(0.5)
    pdf.line(12, y, 198, y)
    y += 4

    # Standing reference table - the open- and closed-model sections each carry one.
    # Gated on the data rather than the section key, so any section can grow one later.
    if extras and extras.get("best_for"):
        y = build_best_for_box(pdf, y, config["color"], extras,
                               _table_heading(section_key, extras))

    if not stories:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(150, 150, 150)
        pdf.set_xy(15, y)
        pdf.cell(180, 8, "No stories in this section today.")
        pdf.set_y(y + 12)
        return

    for idx, story in enumerate(stories):
        title = sanitize_text(story.get("title", "Untitled"))
        # Printed whole: summaries run as long as the story needs (2026-10-02).
        # The 1,200-character clip that stood here is gone, not raised.
        summary = sanitize_text(story.get("summary", ""))
        story_url = story.get("url", "")
        meta_line = _fit_meta_line(pdf, _meta_parts(section_key, story), 178)

        # Measure the block BEFORE drawing so the background box and the page
        # break both match the real rendered height.
        pdf.set_font("Helvetica", "", 8)
        pdf.set_xy(14, y)
        summary_h = pdf.multi_cell(
            178, 3.8, summary, dry_run=True, output="HEIGHT"
        )
        url_h = 5 if story_url else 0
        block_h = 11 + summary_h + url_h + 3

        # Page break if this story will not fit. A block taller than a whole page
        # cannot fit anywhere, so it starts where it is unless the page is nearly
        # full; multi_cell carries the rest of the summary overleaf.
        if y + block_h > 278 and (block_h <= 260 or y > 230):
            pdf.add_page()
            y = pdf.get_y() + 2

        # Alternating background, sized to the measured block but never drawn past
        # the bottom of the page.
        if idx % 2 == 0:
            pdf.set_fill_color(245, 247, 250)
            pdf.rect(10, y, 190, min(block_h - 1, 282 - y), "F")

        # Title (clickable) + relevance stars
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(25, 75, 200)
        pdf.set_xy(14, y + 1)
        relevance = story.get("relevance", 3)
        pdf.cell(155, 5, _fit_title(pdf, title, 155), link=story_url)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(r, g, b)
        pdf.cell(25, 5, render_stars(relevance), align="R")

        # Source / metadata line
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(120, 120, 120)
        pdf.set_xy(14, y + 6)
        pdf.cell(180, 4, meta_line)

        # Summary - full sentences, no truncation
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(60, 60, 60)
        pdf.set_xy(14, y + 11)
        pdf.multi_cell(178, 3.8, summary)

        y = pdf.get_y() + 1
        if story_url:
            pdf.set_font("Helvetica", "U", 7)
            pdf.set_text_color(25, 75, 200)
            pdf.set_xy(14, y)
            # Display text is shortened to fit the column; the link target stays full.
            pdf.cell(180, 4, _fit_url(pdf, story_url, 178), link=story_url)
            y += 5
        y += 3

    pdf.set_y(y)


def build_best_for_box(pdf, y, color, extras, heading="BEST MODEL RIGHT NOW"):
    """Draw a standing "which model is best at what" table.

    Entries come from analyzed_content.json, never from code, so the table is
    rewritten each run instead of ageing into a hardcoded lie. The `as_of` date is
    printed in the heading so a stale table is visible rather than silent.

    Returns the y to continue drawing from; returns it unchanged if there is nothing
    to draw.
    """
    entries = [
        e for e in extras.get("best_for", [])
        if e.get("use_case") and e.get("model")
    ]
    if not entries:
        return y

    r, g, b = color
    label_w, why_w = 34.0, 142.0
    why_x, why_lh = 52.0, 3.4

    # Measure every row before drawing anything, the same way the story blocks do,
    # so the border ends up matching the content it wraps.
    row_heights = []
    for entry in entries:
        pdf.set_font("Helvetica", "", 7)
        why = sanitize_text(entry.get("why", ""))
        pdf.set_xy(why_x, y)
        why_h = (
            pdf.multi_cell(why_w, why_lh, why, dry_run=True, output="HEIGHT")
            if why else 0
        )
        # The label wraps inside its own column, so a long use_case grows the row
        # rather than running into the model line. Measured in the label's own font.
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_xy(16, y)
        label_h = pdf.multi_cell(label_w, 4.6, sanitize_text(entry["use_case"]),
                                 dry_run=True, output="HEIGHT")
        row_heights.append(max(4.6 + why_h, label_h) + 1.4)
    box_h = 8 + sum(row_heights) + 3

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


def _fit_url(pdf, url, max_w):
    """Shorten a URL's DISPLAY text so it never runs past the column.

    Google News redirect links are hundreds of characters long; printed raw they
    overflow the right margin. The link target is unaffected - only the label.
    """
    label = sanitize_text(url)
    if pdf.get_string_width(label) <= max_w:
        return label
    while label and pdf.get_string_width(label + "...") > max_w:
        label = label[:-1]
    return label + "..."


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


def generate_pdf():
    """Main function: load analyzed content and generate PDF."""
    input_file = os.path.join(TMP_DIR, "analyzed_content.json")

    if not os.path.exists(input_file):
        print("ERROR: analyzed_content.json not found. Run analyze_and_categorize.py first.")
        sys.exit(1)

    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    sections_data = data.get("sections", {})
    section_extras = data.get("section_extras", {})

    print("Generating PDF...")

    # Create PDF
    pdf = GlobalAINewsPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Cover page
    pdf.add_page()
    build_cover_page(pdf, sections_data, section_extras)

    # Section pages. Sections with nothing to show are skipped entirely rather than
    # spending a page on "No stories in this section today." - Quantum + AI is absent
    # six days a week by design, so it used to burn a page and a TOC slot on each of
    # them. A section that carries extras (the open-model reference table) still
    # renders even with no stories, because the table is the point.
    for section_key in SECTION_ORDER:
        stories = sections_data.get(section_key, [])
        if not _section_renders(section_key, sections_data, section_extras):
            continue
        pdf.add_page()
        build_section(pdf, section_key, stories, section_extras.get(section_key))

    # Save
    os.makedirs(TMP_DIR, exist_ok=True)
    pdf.output(OUTPUT_FILE)

    file_size = os.path.getsize(OUTPUT_FILE) / 1024
    total_stories = sum(len(sections_data.get(s, [])) for s in SECTION_ORDER)

    print(f"\nPDF generated: {OUTPUT_FILE}")
    print(f"  Size: {file_size:.0f} KB")
    print(f"  Pages: {pdf.page_no()}")
    print(f"  Stories: {total_stories}")

    return OUTPUT_FILE


if __name__ == "__main__":
    generate_pdf()
