#!/usr/bin/env python3
"""Submit one new Prime snapshot response to the existing Google Form."""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

FORM_HOST = "docs.google.com"
USER_AGENT = {"User-Agent": "HumanVibe-Prime-Snapshot/1.0"}
FORM_PATH = re.compile(
    r"(/forms/(?:u/\d+/)?d/(?:e/)?[A-Za-z0-9_-]+)/(?:viewform|formResponse|editResponse)/?"
)
FIELDS = {
    "entry.1699301106": "run_id",
    "entry.807518215": "marker",
    "entry.465536805": "sequence",
    "entry.1756592575": "total",
    "entry.414143502": "snapshot",
}


class FreshForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = None
        self.hidden = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form" and self.action is None:
            self.action = attrs.get("action")
        if tag == "input" and attrs.get("type") == "hidden":
            name = attrs.get("name")
            if name in {"fvv", "fbzx", "pageHistory", "partialResponse"}:
                self.hidden[name] = attrs.get("value", "")


def form_endpoint(url, endpoint):
    parts = urllib.parse.urlsplit(url)
    match = FORM_PATH.fullmatch(parts.path)
    if parts.scheme != "https" or parts.netloc != FORM_HOST or not match:
        raise ValueError("Expected a Google Forms responder URL")
    # Never transfer the response edit token, query or fragment into a submission.
    return f"https://{FORM_HOST}{match[1]}/{endpoint}"


def append_snapshot(form_url, payload):
    view = urllib.request.Request(form_endpoint(form_url, "viewform"), headers=USER_AGENT)
    with urllib.request.urlopen(view, timeout=30) as response:
        view_url = response.geturl()
        parser = FreshForm()
        parser.feed(response.read().decode("utf-8", errors="replace"))

    target = form_endpoint(view_url, "formResponse")
    action = urllib.parse.urljoin(view_url, parser.action or "")
    if not urllib.parse.urlsplit(action).path.endswith("/formResponse") or form_endpoint(action, "formResponse") != target:
        raise ValueError("Fresh Google Form did not expose its standard submission endpoint")

    data = {**parser.hidden, **{entry: payload[key] for entry, key in FIELDS.items()}}
    request = urllib.request.Request(
        target, data=urllib.parse.urlencode(data).encode("utf-8"), method="POST",
        headers={**USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read().decode("utf-8", errors="replace")
        status = response.status
    if status != 200 or not any(marker in body for marker in (
        "Your response has been recorded", "Edit your response", "Submit another response",
    )):
        raise ValueError(f"Google Form append confirmation missing (HTTP {status}); check the sheet")


def main():
    # Re-running an Actions job can replay a POST that already reached Google.
    if os.environ.get("GITHUB_RUN_ATTEMPT", "1") != "1":
        raise SystemExit("Duplicate Form submission refused on workflow rerun; check the ingress sheet")
    form_url = os.environ.get("PRIME_SNAPSHOT_FORM_URL") or os.environ.get("PRIME_SNAPSHOT_EDIT_URL")
    if not form_url:
        raise SystemExit("Missing Google Form responder URL")
    payload = json.loads(Path("prime_snapshot_payload.json").read_text(encoding="utf-8"))
    try:
        append_snapshot(form_url, payload)
    except urllib.error.HTTPError as error:
        raise SystemExit(f"Google Forms returned HTTP {error.code}; check the sheet before a retry") from None
    except (urllib.error.URLError, TimeoutError):
        raise SystemExit("Google Forms transport failed; check the sheet before a retry") from None
    except ValueError as error:
        raise SystemExit(str(error)) from None
    print(f"FORM_APPEND_OK run_id={payload['run_id']} marker={payload['marker']}")


if __name__ == "__main__":
    main()
