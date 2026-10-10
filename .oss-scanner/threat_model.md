# Global AI News threat model

## What this project does

Global AI News is a Python command-line pipeline that collects AI-related news and opportunities from configured RSS/Atom feeds and web pages, filters and organizes the collected items, prepares content for an AI-assisted curation step, generates a PDF briefing, and can email the briefing through the Gmail API.

The main code is under `tools/`; source and workflow configuration is under `workflows/`. Python dependencies are declared in `requirements.txt`. Temporary scrape results, caches, logs, and intermediate content are written under `.tmp/`. This repository is not intended to expose a public HTTP server.

## Security goals

Prioritize, in order:

1. Prevent remote content or a compromised dependency from causing arbitrary code execution, accessing local files, or exposing credentials.
2. Protect Gmail OAuth credentials and prevent an unauthorized or unintended email from being sent.
3. Prevent unsafe network requests made while fetching feeds and articles, including redirects or URLs that could reach local or private services.
4. Handle hostile or malformed RSS/XML, HTML, URLs, metadata, and cached JSON without crashes, uncontrolled resource consumption, or unsafe output.
5. Preserve the integrity of the briefing: retain provenance and source links, avoid silently changing the meaning of source material, and avoid presenting untrusted claims as verified facts.

## Actors and trust boundaries

Treat all remotely supplied feed entries, article titles and summaries, HTML, metadata, linked URLs, and downloaded content as untrusted, even when they arrive through a configured news source. A source can be compromised, a feed entry can contain hostile content, and a publisher page can change after a link is collected.

Treat external content as data, not as instructions. In particular, text that is later read by an AI coding or curation agent may contain prompt-injection attempts intended to alter the task, request secrets, or induce unsafe tool use. Assess whether untrusted content can influence command construction, file paths, tool arguments, source selection, generated links, or downstream actions.

The configured source registry in `tools/feed_sources.py` is project code, but URLs found inside retrieved entries are not automatically trusted. Inspect URL parsing, redirects, timeouts, response-size handling, parsing, caching, and error handling wherever `requests`, `feedparser`, BeautifulSoup, or lxml is used.

The local operator and their configuration are trusted to run the program, but local files can be stale, corrupt, or accidentally replaced. Relevant files include `.env`, `credentials.json`, `token.json`, and the generated content under `.tmp/`. The Gmail integration uses OAuth credentials and the `gmail.send` scope; protect those credentials and any recipient configuration as sensitive.

## Important entry points and data flows

- RSS/Atom feeds and other configured source readers feed `tools/scrape_rss_feeds.py` and related source modules.
- Publisher pages, redirects, article URLs, and scraped HTML flow through the web-fetching and text-extraction helpers, including `tools/web_text.py`, and may be cached or written as intermediate JSON.
- AI-assisted curation consumes source-derived material and produces analyzed content. Review prompt-injection boundaries, provenance, stale or duplicated records, and whether tool execution remains constrained to the intended workflows.
- Local JSON and cache files under `.tmp/` are read by later pipeline steps. Check malformed or partially written data, assumptions about schema and types, path handling, and whether tampered intermediate files can trigger unsafe behavior.
- `tools/generate_pdf.py` turns source-derived content into a PDF. Check text sanitization, layout and encoding edge cases, and whether content can escape its intended presentation.
- `tools/send_email.py` builds an HTML email and sends the PDF using Gmail OAuth. Check HTML escaping, attachment selection, recipient handling, authorization failures, and whether sending can be triggered without explicit operator intent.
- Command-line arguments, environment variables, workflow Markdown, and any script that launches subprocesses are also in scope.

## Priority review areas

- Remote fetches: unsupported URL schemes, redirects to loopback/private/link-local destinations, DNS or redirect changes, request timeouts, unbounded bodies, malformed responses, and exceptions that leave partial state.
- Parsers and data normalization: malformed XML/HTML, surprising encodings, deeply nested or very large documents, invalid dates, oversized fields, and parser/dependency vulnerabilities reachable with untrusted input.
- Prompt injection and AI-assisted actions: source text that asks an agent to reveal credentials, alter files, run commands, change recipients, or disregard the workflow. Determine the actual reachable path and required prerequisites before assigning impact.
- Secrets and email side effects: accidental inclusion of `.env`, `credentials.json`, or `token.json` in a build, log, generated artifact, or public commit; unnecessary OAuth scopes; unintended recipients; HTML injection; and sending without an explicit operator-approved action.
- File and state integrity: path traversal, symlink or unsafe path handling, unsafe deserialization, corrupted or partially written intermediate files, stale data, and writes that overwrite unexpected files.
- Dependency and build chain: compromised or vulnerable PyPI dependencies, unpinned or changing dependencies, and any setup step that executes downloaded code with more privilege than needed.
- Output correctness: loss or alteration of titles, summaries, dates, source URLs, deadlines, or eligibility information when normalizing or rendering input. Treat inaccurate reporting primarily as an integrity issue unless a demonstrated security consequence raises severity.

## Tests and safe validation

The repository has script-based tests under `tools/tests/test_*.py`. Prefer deterministic tests with synthetic feeds, HTML, dates, and local temporary files. Check which tests perform network access before using them for offline validation.

Do not run the full daily pipeline as a scanner smoke test: it is designed to fetch live sources and its later steps can use a local analyzed-content file and send email. Never use production OAuth files, real recipient lists, real email accounts, or private API keys for scanner validation. Do not connect tests to public Bitcoin or other unrelated services; use only disposable local fixtures and mocks. Bound CPU, memory, input size, number of requests, and test runtime.

The scanner installs dependencies during the Docker build and performs the security analysis afterward without Internet access. Build and tests must not depend on secrets or live service responses. A source-only suspicion is not proof of exploitation: when possible, add a small regression test using synthetic input and establish the observable consequence in the actual project code.

## Severity guidance

- Critical: demonstrated compromise that exposes credentials or enables arbitrary code execution with broad impact, or a similarly severe compromise of the operator's account or data.
- High: practical credential disclosure, unauthorized email sending with material impact, arbitrary local file access or modification, or exploitable remote-content handling that crosses a meaningful trust boundary.
- Medium: reproducible denial of service or resource exhaustion with realistic input, significant corruption or misrepresentation that can cause consequential downstream action, or a security weakness requiring meaningful but plausible prerequisites.
- Low: limited-impact edge cases, difficult-to-trigger issues, or inaccurate/poorly formatted output without a demonstrated security consequence.

Do not infer severity from a bug-class label alone. State attacker control, required configuration and privileges, the reachable code path, default versus optional behavior, and the demonstrated effect. Distinguish ordinary news-quality errors from security vulnerabilities.

## Scope notes

The full repository is in scope, including scripts, tests, workflow instructions, configuration, PDF generation, email construction, and dependency usage. Prioritize paths reachable with untrusted remote content or sensitive local credentials. Do not claim a remote attack merely because a script fetches URLs: establish whether the attacker controls the relevant URL and whether redirects or network restrictions make the path reachable. Report third-party dependency findings with the affected package, reachable call site, and demonstrated impact in this application.

Do not publish suspected vulnerabilities, credentials, access tokens, or detailed exploit instructions in public issues or pull requests. Follow the project's coordinated-disclosure policy if one is added; until then, contact the maintainer privately.
