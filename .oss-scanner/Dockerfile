# Security-scanner build environment for Global AI News.
# Dependencies are installed during image build; the audit runs afterward offline.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /src

# Install the project's declared runtime and test dependencies.
COPY requirements.txt /src/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /src/requirements.txt

# The scanner supplies the repository checkout as the build context.
COPY . /src

# Compile only; do not run the production pipeline (which scrapes the Internet
# and can send mail through Gmail OAuth credentials).
RUN python -m compileall -q /src/tools

# Run the project's self-contained script tests with a timeout per test.
# These tests should not require live feeds, API keys, OAuth tokens, or email.
RUN set -eu; \
    for test_file in /src/tools/tests/test_*.py; do \
        echo "===== Running ${test_file} ====="; \
        timeout --signal=TERM --kill-after=5s 180s python "${test_file}"; \
    done

# No CMD is needed: the scanner opens an interactive shell in the built image.
