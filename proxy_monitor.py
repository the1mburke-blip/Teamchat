"""Watch open GitHub issues for ICARUS directives and log their detection."""

import json
import logging
import os
import re
import signal
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


POLL_SECONDS = 60
DIRECTIVE = re.compile(
    r"^\s*(\[ICARUS SUPERVISORY DIRECTIVE\]|ICARUS_RUN)(?=\s|$)",
    re.IGNORECASE | re.MULTILINE,
)


def read_directives(repo, token):
    directives = set()
    page = 1
    while True:
        request = Request(
            f"https://api.github.com/repos/{repo}/issues?state=open&per_page=100&page={page}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "icarus-proxy-monitor",
            },
        )
        with urlopen(request, timeout=15) as response:
            issues = json.load(response)
            has_next_page = 'rel="next"' in response.headers.get("Link", "")
        if not isinstance(issues, list):
            raise ValueError("Expected a list of issues")
        for issue in issues:
            if "pull_request" in issue:
                continue
            for field in ("title", "body"):
                for match in DIRECTIVE.finditer(issue.get(field) or ""):
                    directives.add((issue["number"], match.group(1).upper()))
        if not has_next_page:
            return directives
        page += 1


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    repo = os.environ.get("TARGET_REPO", "").strip()
    token = os.environ.get("GH_TOKEN", "").strip()
    if not token or not re.fullmatch(r"[\w-]+/(?!\.{1,2}$)[\w.-]+", repo, re.ASCII):
        logging.error("Set GH_TOKEN and TARGET_REPO (owner/repo)")
        return 2
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    logging.info("Watching open issues in %s", repo)
    previous = set()
    while True:
        delay = POLL_SECONDS
        try:
            current = read_directives(repo, token)
        except HTTPError as error:
            logging.warning("GitHub issue poll returned HTTP %s", error.code)
            if error.code in (401, 404):
                return 1
            retry_after = error.headers.get("Retry-After", "")
            reset = error.headers.get("X-RateLimit-Reset", "")
            if retry_after.isdecimal():
                delay = max(delay, int(retry_after))
            if error.headers.get("X-RateLimit-Remaining") == "0" and reset.isdecimal():
                delay = max(delay, int(reset) + 1 - time.time())
        except (OSError, ValueError):
            logging.warning("GitHub issue poll failed")
        else:
            for number, tag in sorted(current - previous):
                logging.info("Directive detected in issue #%s (%s)", number, tag)
            previous = current
        time.sleep(delay)


if __name__ == "__main__":
    sys.exit(main())
