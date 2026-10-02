"""Cases for the opportunity qualification gate in scrape_rss_feeds.py.

Every headline here is real - taken from the Google News opportunity feeds when
they were probed on 2026-09-07 - except the IndiaAI line, which is the example
that prompted the section rebuild, and a handful of hand-written near-misses.

Run: python3 tools/tests/test_opportunity_gate.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrape_rss_feeds import qualifies_as_opportunity

QUALIFIES = [
    "US Marines to Launch 'AI Hackathon' Seeking Smarter Ways to Train for War",
    "OpenCV Launches New AI Competition powered by Amazon Web Services",
    "Kurdistan Launches Its First National AI Competition With $30,000 in Prizes",
    "Heilbronn AI Fellowship 2027 for International Postdoctoral Researchers",
    "AI Alignment Foundation Opens 8-Week AI Safety Research Fellowship with $12,000 Stipend",
    "Apply Now: Google Africa Applied AI Lab for Founders",
    "Call for Applications: Experience AI Cohort for African NGOs",
    # "Acceleration Programs", not "accelerator" - government schemes phrase it
    # this way, and the gate missed this exact headline on the first attempt.
    "IndiaAI Startups Global: International Acceleration Programs for Indian AI Startups",
    "MeitY opens applications for its AI startup programme",
]

REJECTED = [
    # Already decided - nothing left to enter.
    "TASKING, Infineon, and DLR Earn Top AWS Hackathon Award for Automotive AI Workflow",
    "Team wins the AI hackathon with a translation app",
    "IIT students won this year's data challenge",
    # AI, but no entry mechanism - these are what wrongly filled the section before.
    "Product Hunt's AI category is taking narrow, single-purpose tools",
    "r/LocalLLaMA is where local-AI tools get their first real users",
    "Adding a model to llama.cpp is a visible open-source contribution channel",
    "Enterprise AI fails for lack of a structured knowledge layer, paper argues",
    # An entry mechanism, but not AI.
    "Applications open for 2027 Business Development Opportunity Grant",
    # The weak terms in their ordinary English sense.
    "Anthropic's IPO Will Be Huge - Here Are the Challenges Investors Should Watch",
    "Dream's Cyber AI Tops Berkeley Benchmark as Specialized Models Challenge Frontier Systems",
    "AI competition heats up as Google and OpenAI trade blows",
    "From dance floor to war: China readies humanoid robots for combat",
]


def main():
    failures = []
    for title in QUALIFIES:
        if not qualifies_as_opportunity(title):
            failures.append(("expected QUALIFY", title))
    for title in REJECTED:
        if qualifies_as_opportunity(title):
            failures.append(("expected REJECT ", title))

    total = len(QUALIFIES) + len(REJECTED)
    for reason, title in failures:
        print(f"  FAIL [{reason}] {title}")
    print(f"{total - len(failures)}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
