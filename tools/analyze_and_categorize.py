"""
Data contract and utilities for the analysis step.
The actual analysis is performed by the Claude Code agent (Opus 4.6) directly,
NOT via an API call. The agent reads scraped data, reasons about it, and writes
the output JSON using save_analyzed_content().

Reads: .tmp/rss_articles.json, .tmp/youtube_trending.json
Writes: .tmp/analyzed_content.json

All 16 sections get equal treatment (3-8 stories each).
"""

import json
import os
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(PROJECT_ROOT, ".tmp")
OUTPUT_FILE = os.path.join(TMP_DIR, "analyzed_content.json")

# The 16 sections for the PDF (all equal priority, 3-8 stories each)
SECTIONS = [
    "ai_music_business_news",
    "ai_music_copyright_laws",
    "global_ai_news",
    "indian_ai_industry",
    "product_showcase_opportunities",
    "anthropic_claude_news",
    "elon_musk_ai_vision",
    "unaddressed_ai_problems",
    "ai_business_opportunities",
    "quantum_ai_research",
    "new_ai_tools",
    "ai_model_benchmarks",
    "ai_business_automation",
    "ai_self_improvement_rsi",
    "viral_video_landscape",
    "youtube_ai_landscape",
]

SECTION_LABELS = {
    "ai_music_business_news": "AI Music Business News",
    "ai_music_copyright_laws": "Copyright & Laws in AI Music Business",
    "global_ai_news": "Global AI News",
    "indian_ai_industry": "Indian AI Industry",
    "product_showcase_opportunities": "AI Product Showcase Opportunities",
    "anthropic_claude_news": "Claude Model Updates",
    "elon_musk_ai_vision": "Elon Musk's AI Vision",
    "unaddressed_ai_problems": "Unaddressed AI Problems",
    "ai_business_opportunities": "AI Business Opportunities",
    "quantum_ai_research": "Quantum + AI",
    "new_ai_tools": "New AI Tools",
    "ai_model_benchmarks": "AI Model Benchmarks",
    "ai_business_automation": "AI Automation & Businesses",
    "ai_self_improvement_rsi": "AI Self-Improvement (RSI)",
    "viral_video_landscape": "Viral Video Landscape",
    "youtube_ai_landscape": "YouTube AI Landscape",
}


def load_scraped_data():
    """Load all scraped data files from .tmp/"""
    data = {"rss_articles": [], "youtube_videos": []}

    rss_file = os.path.join(TMP_DIR, "rss_articles.json")
    if os.path.exists(rss_file):
        with open(rss_file, "r", encoding="utf-8") as f:
            rss_data = json.load(f)
            data["rss_articles"] = rss_data.get("articles", [])
            print(f"Loaded {len(data['rss_articles'])} RSS articles")

    yt_file = os.path.join(TMP_DIR, "youtube_trending.json")
    if os.path.exists(yt_file):
        with open(yt_file, "r", encoding="utf-8") as f:
            yt_data = json.load(f)
            data["youtube_videos"] = yt_data.get("videos", [])
            print(f"Loaded {len(data['youtube_videos'])} YouTube videos")

    return data


def save_analyzed_content(sections_data, total_items):
    """Save agent-produced analysis to the standard output file.

    Args:
        sections_data: dict with 16 section keys, each containing a list of story dicts
        total_items: int, total number of raw items that were analyzed
    """
    os.makedirs(TMP_DIR, exist_ok=True)

    output = {
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "total_items_analyzed": total_items,
        "sections": sections_data,
        "section_labels": SECTION_LABELS,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nAnalysis saved to {OUTPUT_FILE}")
    print("Section breakdown:")
    for section in SECTIONS:
        count = len(sections_data.get(section, []))
        label = SECTION_LABELS[section]
        print(f"  [{count:>2} stories] {label}")

    return output


if __name__ == "__main__":
    print("This module provides data contract and utilities for the analysis step.")
    print("The actual analysis is performed by the Claude Code agent (Opus 4.6).")
    print(f"\nExpected output: {OUTPUT_FILE}")
    print(f"Sections: {len(SECTIONS)}")
    for key, label in SECTION_LABELS.items():
        print(f"  - {key}: {label}")
