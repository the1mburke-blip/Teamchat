#!/usr/bin/env python3
"""Read authorized Teamchat task directives and publish delegation receipts."""

import datetime
import json
import os
import sys
import urllib.request


TASK_HEADER = "[TASK_INCOMING]"
DISPATCH_HEADER = "[ICARUS DISPATCH]"
TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
CHAIRS = {"[WORK]", "[SOL]"}
PAGE_SIZE = 100
STATUS_PATH = "icarus_status.json"
LEDGER_PATH = "RUN_LOG.jsonl"


def call_github_api(url, token, method="GET", payload=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ICARUS-Supervisory-Runner",
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"HTTP {response.status}")
            return json.load(response), response.headers.get("Link", "")
    except (OSError, ValueError, RuntimeError) as error:
        raise RuntimeError(f"{method} {url}: {error}") from error


def fetch_comments(url, token):
    comments = []
    page = 1
    while True:
        batch, links = call_github_api(f"{url}?per_page={PAGE_SIZE}&page={page}", token)
        if not isinstance(batch, list):
            raise ValueError("GitHub returned an invalid issue comment list")
        comments.extend(batch)
        if not any(link.strip().endswith('rel="next"') for link in links.split(",")):
            return comments
        page += 1


def parse_field(line):
    label, separator, value = line.partition(":")
    if not separator:
        return "", ""
    return " ".join(label.casefold().replace("_", " ").split()), value.strip()


def find_pending_task(comments):
    dispatched = set()
    pending = None
    # GitHub returns ascending comment IDs. Scanning backward only matches later receipts.
    for comment in reversed(comments):
        body = comment.get("body") or ""
        header, _, fields = body.partition("\n")
        trusted = comment.get("author_association") in TRUSTED_ASSOCIATIONS
        author = (comment.get("user") or {}).get("login")
        if header.strip() == DISPATCH_HEADER and (trusted or author == "github-actions[bot]"):
            label, task_id = parse_field(fields.lstrip().partition("\n")[0])
            if label == "task id" and task_id:
                dispatched.add(task_id)
        elif header.strip() == TASK_HEADER and trusted:
            id_line, _, remainder = fields.lstrip().partition("\n")
            chair_line, _, scope_field = remainder.lstrip().partition("\n")
            id_label, task_id = parse_field(id_line)
            chair_label, chair = parse_field(chair_line)
            scope_label, scope = parse_field(scope_field)
            if (
                id_label == "task id"
                and len(task_id.split()) == 1
                and task_id not in dispatched
                and chair_label == "target chair"
                and chair in CHAIRS
                and scope_label in {"scope", "scope instruction", "directive"}
                and scope
            ):
                pending = task_id, chair, scope
    return pending


def append_status(record):
    try:
        with open(STATUS_PATH, encoding="utf-8") as status_file:
            history = json.load(status_file)
    except FileNotFoundError:
        history = []
    if isinstance(history, dict):
        history = [history]
    history.append(record)

    temp_path = f"{STATUS_PATH}.tmp"
    with open(temp_path, "w", encoding="utf-8") as status_file:
        json.dump(history, status_file, indent=2)
        status_file.write("\n")
    os.replace(temp_path, STATUS_PATH)


def append_ledger(record):
    with open(LEDGER_PATH, "a", encoding="utf-8") as ledger:
        ledger.write(json.dumps(record) + "\n")


def main():
    timestamp = datetime.datetime.now(datetime.timezone.utc)
    entry = {
        "timestamp_utc": timestamp.isoformat(),
        "run_id": f"RUN-{timestamp:%Y%m%d-%H%M%SZ}",
    }
    try:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise RuntimeError("GITHUB_TOKEN is missing or empty")
        repo = os.getenv("GITHUB_REPOSITORY", "the1mburke-blip/Teamchat")
        issue = int(os.getenv("ICARUS_ISSUE_NUMBER", "6"))
        url = f"https://api.github.com/repos/{repo}/issues/{issue}/comments"

        task = find_pending_task(fetch_comments(url, token))
        status = {"status": "PASS", "intake_state": "IDLE"}
        if task:
            task_id, chair, scope = task
            entry.update(task_id=task_id, delegated_to=chair)
            body = (
                f"{DISPATCH_HEADER}\n"
                f"Task ID: {task_id}\n"
                f"Target Chair: {chair}\n"
                f"Directive: {scope}\n"
                "Budget: €0.00 | Repair Leash: 1 attempt"
            )
            receipt, _ = call_github_api(url, token, "POST", {"body": body})
            comment_id = receipt.get("id")
            if type(comment_id) is not int or comment_id <= 0:
                raise ValueError("GitHub did not return a valid dispatch comment ID")
            entry["dispatch_comment_id"] = comment_id
            status.update(
                intake_state="DELEGATED",
                task_id=task_id,
                delegated_to=chair,
                dispatch_comment_id=comment_id,
            )

        append_status(status)
        append_ledger({**entry, **status})
        print(json.dumps({**entry, **status}))
        return 0
    except Exception as error:
        failure = {**entry, "status": "FAIL", "details": str(error)}
        print(json.dumps(failure), file=sys.stderr)
        append_ledger(failure)
        return 1


if __name__ == "__main__":
    sys.exit(main())
