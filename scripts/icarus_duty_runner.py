#!/usr/bin/env python3
"""Read authorized Teamchat task directives and publish delegation receipts."""

import datetime
import json
import os
import re
import sys
import urllib.request


TASK_HEADER = "[TASK_INCOMING]"
DISPATCH_HEADER = "[ICARUS DISPATCH]"
MONITOR_ONLY_MARKER = re.compile(
    r"^\s*(\[ICARUS SUPERVISORY DIRECTIVE\]|ICARUS_RUN)(?=\s|$)",
    re.IGNORECASE | re.MULTILINE,
)
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


def fetch_pages(url, token):
    items = []
    page = 1
    separator = "&" if "?" in url else "?"
    while True:
        batch, links = call_github_api(f"{url}{separator}per_page={PAGE_SIZE}&page={page}", token)
        if not isinstance(batch, list):
            raise ValueError(f"GitHub returned an invalid list for {url}")
        items.extend(batch)
        if not any(link.strip().endswith('rel="next"') for link in links.split(",")):
            return items
        page += 1


def parse_field(line):
    label, separator, value = line.partition(":")
    if not separator:
        return "", ""
    return " ".join(label.casefold().replace("_", " ").split()), value.strip()


def dispatched_task_ids(comments):
    dispatched = set()
    for comment in comments:
        body = comment.get("body") or ""
        header, _, fields = body.partition("\n")
        trusted = comment.get("author_association") in TRUSTED_ASSOCIATIONS
        author = (comment.get("user") or {}).get("login")
        if header.strip() == DISPATCH_HEADER and (trusted or author == "github-actions[bot]"):
            label, task_id = parse_field(fields.lstrip().partition("\n")[0])
            if label == "task id" and task_id:
                dispatched.add(task_id)
    return dispatched


def parse_task(fields):
    id_line, _, remainder = fields.lstrip().partition("\n")
    chair_line, _, scope_field = remainder.lstrip().partition("\n")
    id_label, task_id = parse_field(id_line)
    chair_label, chair = parse_field(chair_line)
    scope_label, scope = parse_field(scope_field)
    if (
        id_label == "task id"
        and len(task_id.split()) == 1
        and chair_label == "target chair"
        and chair in CHAIRS
        and scope_label in {"scope", "scope instruction", "directive"}
        and scope
    ):
        return task_id, chair, scope
    return None


def inspect_directives(issue, comments, record):
    number = issue["number"]
    sources = [(None, issue), *((comment["id"], comment) for comment in comments)]
    pending = []
    for comment_id, source in sources:
        title = source.get("title") or ""
        body = source.get("body") or ""
        header, _, fields = body.partition("\n")
        if comment_id is not None and header.strip() == DISPATCH_HEADER:
            continue
        markers = {tag.upper() for tag in MONITOR_ONLY_MARKER.findall(f"{title}\n{body}")}
        if header.strip() == TASK_HEADER:
            markers.add(TASK_HEADER)
        elif title.strip() == TASK_HEADER:
            markers.add(TASK_HEADER)
            fields = body
        if source.get("author_association") not in TRUSTED_ASSOCIATIONS:
            record["authorization_rejections"] += len(markers)
            continue
        origin = {"issue_number": number, "source_comment_id": comment_id}
        if TASK_HEADER in markers:
            markers.remove(TASK_HEADER)
            task = parse_task(fields)
            if task:
                record["eligible_directives_detected"] += 1
                pending.append((origin, task))
        for marker in sorted(markers):
            record["eligible_directives_detected"] += 1
            record["monitor_only_events"].append({**origin, "marker": marker})
    return pending


def monitor_issues(repo, mailbox, token, record):
    issues_url = f"https://api.github.com/repos/{repo}/issues"
    outbox_url = f"{issues_url}/{mailbox}/comments"
    issues = fetch_pages(f"{issues_url}?state=open&sort=created&direction=asc", token)
    open_issues = {issue["number"]: issue for issue in issues if "pull_request" not in issue}
    outbox_comments = fetch_pages(outbox_url, token)
    dispatched = dispatched_task_ids(outbox_comments)
    pending = []

    # Finish discovery and read all prior receipts before making any dispatch writes.
    for number, issue in sorted(open_issues.items()):
        if number == mailbox:
            comments = outbox_comments
        elif issue.get("comments") == 0:
            comments = []
        else:
            comments = fetch_pages(f"{issues_url}/{number}/comments", token)
        pending.extend(inspect_directives(issue, sorted(comments, key=lambda c: c["id"]), record))
        record["issue_numbers_inspected"].append(number)

    # Issue #6 remains the shared outbox. Its receipts also cover closed source issues.
    for origin, (task_id, chair, scope) in pending:
        if task_id in dispatched:
            record["duplicate_directives_ignored"] += 1
            continue
        body = (
            f"{DISPATCH_HEADER}\n"
            f"Task ID: {task_id}\n"
            f"Target Chair: {chair}\n"
            f"Directive: {scope}\n"
            "Budget: €0.00 | Repair Leash: 1 attempt"
        )
        if origin["issue_number"] != mailbox:
            body += f"\nSource Issue: #{origin['issue_number']}"
            if origin["source_comment_id"] is not None:
                body += f" (comment {origin['source_comment_id']})"
        receipt, _ = call_github_api(outbox_url, token, "POST", {"body": body})
        comment_id = receipt.get("id")
        if type(comment_id) is not int or comment_id <= 0:
            raise ValueError("GitHub did not return a valid dispatch comment ID")
        dispatched.add(task_id)
        record["dispatch_receipts"].append({
            **origin,
            "task_id": task_id,
            "delegated_to": chair,
            "dispatch_comment_id": comment_id,
        })


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
    status = {
        "monitoring_result": "SUCCESS",
        "issue_numbers_inspected": [],
        "eligible_directives_detected": 0,
        "duplicate_directives_ignored": 0,
        "authorization_rejections": 0,
        "monitor_only_events": [],
        "dispatch_receipts": [],
        "first_processing_error": None,
    }
    try:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise RuntimeError("GITHUB_TOKEN is missing or empty")
        repo = os.getenv("GITHUB_REPOSITORY", "the1mburke-blip/Teamchat")
        mailbox = int(os.getenv("ICARUS_ISSUE_NUMBER", "6"))
        monitor_issues(repo, mailbox, token, status)
    except Exception as error:
        status.update(monitoring_result="FAILURE", first_processing_error=str(error))

    failed = status["first_processing_error"] is not None
    receipts = status["dispatch_receipts"]
    status["open_issues_inspected"] = len(status["issue_numbers_inspected"])
    status["new_tasks_dispatched"] = len(receipts)
    if failed:
        status["intake_state"] = "ERROR"
    elif receipts:
        status["intake_state"] = "DELEGATED"
    else:
        status["intake_state"] = "IDLE"
    record = {**entry, **status}
    append_ledger(record)
    append_status(record)
    print(json.dumps(record), file=sys.stderr if failed else sys.stdout)
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
