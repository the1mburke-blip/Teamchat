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
CLAIM_HEADER = "[ICARUS CLAIM]"
ADJUDICATION_HEADER = "[ICARUS ADJUDICATION: PASS]"
WORK_RECEIPT = "[WORK] EXECUTION RECEIPT"
ECHO_DIRECTIVE = "Echo test for task intake and worker delegation verification."
MONITOR_ONLY_MARKER = re.compile(
    r"^\s*(\[ICARUS SUPERVISORY DIRECTIVE\]|ICARUS_RUN)(?=\s|$)",
    re.IGNORECASE | re.MULTILINE,
)
TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
CHAIRS = {"[WORK]", "[SOL]"}
READY = {"REQUESTED", "READY", "TODO", "BACKLOG", "OPEN"}
UNAVAILABLE = {
    "BLOCKED", "IN PROGRESS", "CLAIMED", "EXECUTING", "VERIFYING", "WAITING",
    "WAITING FOR RECEIPT", "ADJUDICATED", "DONE", "CLOSED", "PASS", "FAIL",
    "PARTIAL", "SUPERSEDED", "DUPLICATE", "WONTFIX", "ON HOLD", "DRAFT",
    "NEEDS OWNER", "CANCELLED",
}
PRIORITY = {"CRITICAL": 0, "URGENT": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
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


def comment_packets(comments, header, *, bot_only=False):
    for comment in comments:
        body = comment.get("body") or ""
        first, _, fields = body.partition("\n")
        is_bot = (comment.get("user") or {}).get("login") == "github-actions[bot]"
        trusted = comment.get("author_association") in TRUSTED_ASSOCIATIONS
        if first.strip() == header and (is_bot or (trusted and not bot_only)):
            pairs = [parse_field(line) for line in fields.splitlines() if ":" in line]
            packet = dict(pairs)
            if len(pairs) == len(packet) and packet.get("task id"):
                yield comment, packet


def post_comment(url, token, body):
    receipt, _ = call_github_api(url, token, "POST", {"body": body})
    comment_id = receipt.get("id")
    if type(comment_id) is not int or comment_id <= 0:
        raise ValueError("GitHub did not return a valid issue comment ID")
    return comment_id


def issue_field(issue, name):
    values = re.findall(rf"^\[{name}\][ \t]+([^\n]+)", issue.get("body") or "", re.I | re.M)
    # Multiple conflicting fields are ambiguous and must not grant authority.
    return values[0].strip() if len(values) == 1 else ("AMBIGUOUS" if values else "")


def normalized(value):
    return " ".join(re.sub(r"[-_]", " ", value.upper()).split())


def backlog_candidate(issue):
    if (issue.get("state") != "open" or issue.get("assignees")
            or issue.get("assignee") or issue.get("author_association") not in TRUSTED_ASSOCIATIONS):
        return None
    labels = {normalized(label["name"]) for label in issue.get("labels", [])}
    states = {re.sub(r"^STATUS\s*:\s*", "", label) for label in labels}
    title = " ".join((issue.get("title") or "").split())
    tags = {normalized(tag) for tag in re.findall(r"\[([^\]]+)\]", title)}
    state = normalized(re.split(r"\s+[—–-]\s+", issue_field(issue, "STATUS"), maxsplit=1)[0])
    active_owner = re.split(r"\s+[—–-]\s+", issue_field(issue, "ACTIVE_OWNER"), maxsplit=1)[0]
    chair = issue_field(issue, "TO") or "[WORK]"
    if (not title or (states | tags | {state}) & UNAVAILABLE
            or not ((states | tags | {state}) & READY)
            or (state and state not in READY)
            or active_owner.strip("[]").upper() not in {"", "NONE"}
            or chair not in CHAIRS):
        return None
    cost = issue_field(issue, "COST")
    if cost and not re.match(r"^(?:€|EUR\s*)0(?:[.,]00)?(?=\s|[.;,](?!\d)|$)", cost, re.I):
        return None
    priorities = []
    for value in labels | tags | {normalized(issue_field(issue, "PRIORITY"))}:
        value = re.sub(r"^PRIORITY\s*:\s*", "", value)
        if re.fullmatch(r"P[0-4]", value):
            priorities.append(int(value[1]))
        elif value in PRIORITY:
            priorities.append(PRIORITY[value])
    return min(priorities, default=4), issue["number"], chair, title


def adjudicate_canaries(repo, mailbox, comments, dispatches, outbox_url, token, record):
    adjudicated = {packet["task id"] for _, packet in
                   comment_packets(comments, ADJUDICATION_HEADER, bot_only=True)}
    intakes = {
        packet["task id"]: (comment, packet)
        for comment, packet in comment_packets(comments, TASK_HEADER)
        if comment.get("author_association") == "OWNER"
        and packet.get("directive") == ECHO_DIRECTIVE
        and packet.get("target chair") == "[WORK]"
    }
    receipts = list(comment_packets(comments, WORK_RECEIPT))
    claims = {comment["id"]: (comment, packet)
              for comment, packet in comment_packets(comments, "[WORK] CLAIMED")}
    link = f"https://github.com/{repo}/issues/{mailbox}#issuecomment-"
    waiting = []
    for dispatch, packet in dispatches:
        task_id = packet["task id"]
        if (not task_id.startswith("CANARY-INTAKE-") or task_id in adjudicated
                or packet.get("target chair") != "[WORK]"
                or packet.get("directive") != ECHO_DIRECTIVE or task_id not in intakes):
            continue
        intake, _ = intakes[task_id]
        owner = (intake.get("user") or {}).get("login")
        for receipt, result in receipts:
            claim_link = result.get("work claim", "")
            claim_id = claim_link.removeprefix(link)
            if not claim_link.startswith(link) or not claim_id.isdecimal() or int(claim_id) not in claims:
                continue
            claim, claim_fields = claims[int(claim_id)]
            if (result["task id"] != task_id or result.get("worker result") != "ECHO_COMPLETE"
                    or result.get("executor") != "ChatGPT Work" or result.get("echo") != ECHO_DIRECTIVE
                    or result.get("owner intake") != link + str(intake["id"])
                    or result.get("icarus dispatch") != link + str(dispatch["id"])
                    or claim_fields["task id"] != task_id
                    or claim_fields.get("dispatch") != link + str(dispatch["id"])
                    or not owner or any(
                        c.get("author_association") != "OWNER" or (c.get("user") or {}).get("login") != owner
                        for c in (claim, receipt))
                    or not intake["id"] < dispatch["id"] < claim["id"] < receipt["id"]):
                continue
            comment_id = post_comment(outbox_url, token, (
                f"{ADJUDICATION_HEADER}\nTask ID: {task_id}\n"
                f"Owner intake: {link}{intake['id']}\nIcarus dispatch: {link}{dispatch['id']}\n"
                f"Work claim: {claim_link}\nWork receipt: {link}{receipt['id']}\n"
                f"Pulse run ID: {os.environ.get('GITHUB_RUN_ID', 'local')}\n"
                "Evidence: authorized source, dispatch, claim and exact echo agree."
            ))
            record["adjudication_receipts"].append({
                "task_id": task_id, "work_receipt_comment_id": receipt["id"],
                "adjudication_comment_id": comment_id,
            })
            adjudicated.add(task_id)
            break
        else:
            waiting.append({"task_id": task_id, "dispatch_comment_id": dispatch["id"]})
    return waiting


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


def dispatch_task(outbox_url, token, origin, task, mailbox, record):
    task_id, chair, scope = task
    body = (
        f"{DISPATCH_HEADER}\nTask ID: {task_id}\nTarget Chair: {chair}\n"
        f"Directive: {scope}\nBudget: €0.00 | Repair Leash: 1 attempt"
    )
    if origin["issue_number"] != mailbox:
        body += f"\nSource Issue: #{origin['issue_number']}"
        if origin["source_comment_id"] is not None:
            body += f" (comment {origin['source_comment_id']})"
    comment_id = post_comment(outbox_url, token, body)
    record["dispatch_receipts"].append({
        **origin, "task_id": task_id, "delegated_to": chair, "dispatch_comment_id": comment_id,
    })


def monitor_issues(repo, mailbox, token, record):
    issues_url = f"https://api.github.com/repos/{repo}/issues"
    outbox_url = f"{issues_url}/{mailbox}/comments"
    issues = fetch_pages(f"{issues_url}?state=open&sort=created&direction=asc", token)
    open_issues = {issue["number"]: issue for issue in issues if "pull_request" not in issue}
    outbox_comments = fetch_pages(outbox_url, token)
    dispatch_packets = [packet for _, packet in comment_packets(outbox_comments, DISPATCH_HEADER)]
    dispatched = {packet["task id"] for packet in dispatch_packets}
    dispatched_sources = {
        int(source[1]) for packet in dispatch_packets
        if (source := re.match(r"^#(\d+)(?:\s|$)", packet.get("source issue", "")))
    }
    pending = []
    candidates = []
    scheduled = os.environ.get("GITHUB_EVENT_NAME") == "schedule"

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
        if scheduled and number != mailbox and (candidate := backlog_candidate(issue)):
            task_id = f"BACKLOG-{number}"
            if task_id not in dispatched and number not in dispatched_sources:
                claim = next((comment for comment, packet in comment_packets(comments, CLAIM_HEADER, bot_only=True)
                              if packet["task id"] == task_id
                              and packet.get("target chair") == candidate[2]), None)
                candidates.append((claim is None, candidate, claim))

    # Explicit operator work overrides automatic selection. Preserve existing packet routing.
    for origin, (task_id, chair, scope) in pending:
        if task_id in dispatched:
            record["duplicate_directives_ignored"] += 1
            continue
        dispatch_task(outbox_url, token, origin, (task_id, chair, scope), mailbox, record)
        dispatched.add(task_id)
    if not scheduled:
        return

    bot_dispatches = list(comment_packets(outbox_comments, DISPATCH_HEADER, bot_only=True))
    record["waiting_canary"] = adjudicate_canaries(
        repo, mailbox, outbox_comments, bot_dispatches, outbox_url, token, record,
    )
    record["waiting_backlog"] = [
        {"task_id": packet["task id"], "dispatch_comment_id": dispatch["id"]}
        for dispatch, packet in bot_dispatches
        if (match := re.fullmatch(r"BACKLOG-(\d+)", packet["task id"])) and int(match[1]) in open_issues
    ]
    if record["adjudication_receipts"]:
        record["loop_state"] = "ADJUDICATED"
        return
    if record["waiting_canary"] or record["waiting_backlog"] or record["dispatch_receipts"]:
        record["loop_state"] = "WAITING_FOR_RECEIPT"
    if record["dispatch_receipts"]:
        return

    # Outstanding receipts are recorded above. Discovery already excludes their dispatched backlog tasks.
    # Resume a previously persisted claim first. The workflow serializes Pulse jobs.
    for _, candidate, claim in sorted(candidates, key=lambda item: (item[0], item[1])):
        _, number, chair, _ = candidate
        current, _ = call_github_api(f"{issues_url}/{number}", token)
        fresh = backlog_candidate(current)
        if fresh != candidate:
            continue
        task_id = f"BACKLOG-{number}"
        claim_id = claim["id"] if claim else post_comment(f"{issues_url}/{number}/comments", token, (
            f"{CLAIM_HEADER}\nTask ID: {task_id}\nTarget Chair: {chair}\n"
            "Budget: €0.00 | Repair Leash: 1 attempt"
        ))
        record["backlog_claim"] = {"issue_number": number, "claim_comment_id": claim_id}
        scope = f"{fresh[3]}. Read the canonical scope and evidence gates in https://github.com/{repo}/issues/{number}."
        dispatch_task(outbox_url, token, {"issue_number": number, "source_comment_id": claim_id},
                      (task_id, chair, scope), mailbox, record)
        record["loop_state"] = "WAITING_FOR_RECEIPT"
        break

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
        "adjudication_receipts": [],
        "waiting_canary": [],
        "waiting_backlog": [],
        "backlog_claim": None,
        "loop_state": "IDLE_SELECT",
        "first_processing_error": None,
    }
    # Twelve slots per day for up to 30 days gives a 360-slot monthly budget.
    cadence_skip = (
        os.environ.get("GITHUB_EVENT_NAME") == "schedule"
        and (timestamp.hour % 2 != 0 or timestamp.day == 31)
    )
    try:
        if cadence_skip:
            status.update(monitoring_result="SKIPPED", loop_state="SKIPPED_CADENCE")
        else:
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
    elif cadence_skip:
        status["intake_state"] = "SKIPPED"
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
