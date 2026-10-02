"""
Master orchestrator for the Global AI News daily pipeline.
Runs all tools in sequence: scrape RSS → analyze → generate PDF → email.
Handles errors gracefully — if one scraper fails, continues with the rest.
"""

import os
import sys
import time
import traceback
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

TMP_DIR = os.path.join(PROJECT_ROOT, ".tmp")
LOG_FILE = os.path.join(TMP_DIR, "pipeline.log")


def log(msg):
    """Print and log a message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_step(name, func):
    """Run a pipeline step with error handling and timing."""
    log(f"STARTING: {name}")
    start = time.time()
    try:
        result = func()
        elapsed = time.time() - start
        log(f"COMPLETED: {name} ({elapsed:.1f}s)")
        return True, result
    except SystemExit as e:
        elapsed = time.time() - start
        log(f"FAILED: {name} (exit code {e.code}) ({elapsed:.1f}s)")
        return False, None
    except Exception as e:
        elapsed = time.time() - start
        log(f"FAILED: {name}: {e} ({elapsed:.1f}s)")
        traceback.print_exc()
        return False, None


def run_pipeline():
    """Run the full daily pipeline."""
    os.makedirs(TMP_DIR, exist_ok=True)

    log("=" * 60)
    log("GLOBAL AI NEWS - DAILY PIPELINE START")
    log("=" * 60)

    pipeline_start = time.time()
    results = {}

    # ── Step 1: Scrape RSS Feeds ──────────────────────────────────────────
    from tools.scrape_rss_feeds import scrape_all_feeds
    ok, data = run_step("Scrape RSS Feeds", scrape_all_feeds)
    results["rss"] = ok

    # ── YouTube scraping removed 2026-09-03 ───────────────────────────────
    # scrape_youtube_trending.py only fed the Viral Video Landscape and YouTube
    # AI Landscape sections. Both were removed when the brief was cut to 10
    # sections, so the ~3,500 quota units it spent per run bought nothing. The
    # tool file is kept in tools/ in case those sections return.

    # ── Check: RSS is now the only input source ───────────────────────────
    if not results.get("rss"):
        log("ABORT: RSS scrape failed. Cannot proceed.")
        return False

    # ── Step 3: Analyze and Categorize ────────────────────────────────────
    # Analysis is now performed by the Claude Code agent (Opus 4.6) directly.
    # The agent reads scraped data, reasons about it, and writes analyzed_content.json.
    # When running via this pipeline script, check if analyzed_content.json exists.
    import json
    analyzed_file = os.path.join(TMP_DIR, "analyzed_content.json")
    if os.path.exists(analyzed_file):
        with open(analyzed_file, "r") as f:
            analyzed = json.load(f)
        section_count = sum(len(v) for v in analyzed.get("sections", {}).values())
        log(f"Step 3 SKIPPED — agent performs analysis directly. Found existing analyzed_content.json ({section_count} stories)")
        results["analyze"] = True
    else:
        log("ABORT: analyzed_content.json not found. Agent must perform analysis before running PDF/email steps.")
        results["analyze"] = False
        return False

    # ── Step 4: Generate PDF ──────────────────────────────────────────────
    from tools.generate_pdf import generate_pdf
    ok, pdf_path = run_step("Generate PDF", generate_pdf)
    results["pdf"] = ok

    if not ok:
        log("ABORT: PDF generation failed. Cannot send email.")
        return False

    # ── Step 5: Send Email ────────────────────────────────────────────────
    from tools.send_email import send_email
    ok, _ = run_step("Send Email", send_email)
    results["email"] = ok

    # ── Summary ───────────────────────────────────────────────────────────
    elapsed = time.time() - pipeline_start
    log("-" * 60)
    log("PIPELINE SUMMARY:")
    for step, status in results.items():
        icon = "OK" if status else "FAIL"
        log(f"  [{icon}] {step}")
    log(f"Total time: {elapsed:.1f}s")

    all_ok = all(results.values())
    if all_ok:
        log("PIPELINE COMPLETED SUCCESSFULLY")
    else:
        log("PIPELINE COMPLETED WITH ERRORS")

    log("=" * 60)
    return all_ok


if __name__ == "__main__":
    success = run_pipeline()
    sys.exit(0 if success else 1)
