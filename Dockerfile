# Image for the ICARUS issue monitor.
FROM python:3.11-slim AS icarus-daemon

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY proxy_monitor.py harness-runner.py ./
COPY icarus/__init__.py ./icarus/__init__.py
COPY icarus/harness/ ./icarus/harness/
COPY dsh/ ./dsh/
USER 1000:1000
ENTRYPOINT ["python3", "proxy_monitor.py"]

# Teamchat / Cordis kernel test & runner image.
# Code is stdlib-only plus pytest (requirements-dev.txt); git is needed by
# dsh.runner / dsh.completion for lease and publish operations.
FROM python:3.12-slim AS harness-tests

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

COPY . .

# Run as non-root; git needs to trust the mounted/copied checkout.
RUN useradd --create-home --uid 1000 app \
    && chown -R app:app /app \
    && git config --system --add safe.directory /app
USER app

# Default: run the offline test suite (mocked HTTP, no API credits).
# Override for real tasks, e.g.:
#   docker run --rm --env-file .env teamchat python -m dsh.runner sample.py "..."
CMD ["python", "-m", "pytest"]
