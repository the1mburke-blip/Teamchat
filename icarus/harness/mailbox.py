"""Publish the physical harness result from a trusted main-branch Actions run."""

import datetime
import itertools
import json
import os
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

from dsh.state_write_gate import NoRedirect, REPOSITORY


ISSUE_URL = f"https://api.github.com/repos/{REPOSITORY}/issues/6"
COMMENTS_URL = f"{ISSUE_URL}/comments"
BOT_ID = 41898282


def request(opener, token, url, payload=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    with opener.open(urllib.request.Request(url, data=data, headers=headers), timeout=20) as response:
        return response.status, json.load(response), response.headers.get("Link", "")


def matching_comment(comment, body):
    return (
        comment.get("body") == body
        and (comment.get("user") or {}).get("id") == BOT_ID
        and str(comment.get("issue_url", "")).casefold() == ISSUE_URL.casefold()
        and bool(comment.get("created_at"))
        and comment.get("created_at") == comment.get("updated_at")
        and type(comment.get("id")) is int
        and comment["id"] > 0
    )


def publish_comment(token, body, since):
    opener = urllib.request.build_opener(NoRedirect())
    for page in itertools.count(1):
        query = urllib.parse.urlencode({"since": since, "per_page": 100, "page": page})
        status, comments, links = request(opener, token, f"{COMMENTS_URL}?{query}")
        if status != 200 or not isinstance(comments, list):
            raise ValueError("Invalid Issue 6 comment listing")
        for comment in comments:
            if matching_comment(comment, body):
                return status, comment["id"], "already_posted"
        if 'rel="next"' not in links:
            break

    status, comment, _ = request(opener, token, COMMENTS_URL, {"body": body})
    if status != 201 or not matching_comment(comment, body):
        raise ValueError("Issue 6 did not return a matching HTTP 201 comment")
    return status, comment["id"], "created"


def writeback(path):
    token = os.getenv("GITHUB_TOKEN")
    run_id = os.getenv("GITHUB_RUN_ID", "")
    sha = os.getenv("GITHUB_SHA", "")
    if (os.getenv("GITHUB_ACTIONS") != "true" or os.getenv("GITHUB_EVENT_NAME") != "push"
            or os.getenv("GITHUB_REPOSITORY") != REPOSITORY
            or os.getenv("GITHUB_REF") != "refs/heads/main"
            or not re.fullmatch(r"[1-9][0-9]*", run_id) or not re.fullmatch(r"[0-9a-f]{40}", sha)):
        raise ValueError("Issue 6 writeback requires a Teamchat main-branch push run")
    if not token:
        raise ValueError("GITHUB_TOKEN is required for Issue 6 writeback")

    path = Path(path)
    record = json.loads(path.read_text(encoding="utf-8"))
    attempt = record["run_attempt"]
    if (record["run_id"] != run_id or record["sha"] != sha or record["event"] != "push"
            or record["ref"] != "refs/heads/main" or not isinstance(attempt, str)
            or not re.fullmatch(r"[1-9][0-9]*", attempt) or int(attempt) > int(os.environ["GITHUB_RUN_ATTEMPT"])):
        raise ValueError("Harness evidence does not match the current push run")

    timestamp = datetime.datetime.fromisoformat(record["timestamp"])
    if timestamp.utcoffset() != datetime.timedelta(0):
        raise ValueError("Harness evidence must carry a UTC timestamp")
    exit_code = record["harness_exit_code"]
    if exit_code is not None and type(exit_code) is not int:
        raise ValueError("Invalid physical harness exit code")
    passed = (exit_code == 0 and record["build_outcome"] == "success"
              and record["harness_outcome"] == "success")
    verdict = "BLOCKED" if exit_code is None else ("PASSED" if passed else "FAILED")
    exit_text = "unavailable" if exit_code is None else str(exit_code)
    body = (
        "[ICARUS HARNESS EVIDENCE]\n"
        f"Run: https://github.com/{REPOSITORY}/actions/runs/{run_id}\n"
        f"Attempt: {attempt}\nSource Commit: {sha}\nTimestamp: {timestamp.isoformat()}\n"
        f"Harness Exit Code: {exit_text}\nStatus: {verdict}"
    )
    status, comment_id, disposition = publish_comment(token, body, timestamp.isoformat())
    result = {"record_type": "harness_mailbox_writeback", "run_id": run_id, "run_attempt": attempt,
              "source_commit": sha, "timestamp": timestamp.isoformat(), "harness_exit_code": exit_code,
              "status": verdict, "http_status": status, "comment_id": comment_id,
              "comment_url": f"https://github.com/{REPOSITORY}/issues/6#issuecomment-{comment_id}",
              "disposition": disposition}
    with path.open("a", encoding="utf-8") as ledger:
        ledger.write(json.dumps(result) + "\n")
    return result


def main(path):
    try:
        print(json.dumps(writeback(path)))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Issue 6 harness writeback failed: {error}", file=sys.stderr)
        return 1
    return 0
