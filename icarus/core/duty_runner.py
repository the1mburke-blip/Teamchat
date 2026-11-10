#!/usr/bin/env python3
"""Read authorized Teamchat task directives and publish delegation receipts.

Execution directives declare one repository-relative `Source File:` field.
Scheduled backlog issues use `[SOURCE_FILE]`. The echo canary has no file.
"""

import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from icarus.core import pilot_state


TASK_HEADER = "[TASK_INCOMING]"
DISPATCH_HEADER = "[ICARUS DISPATCH]"
CLAIM_HEADER = "[ICARUS CLAIM]"
ADJUDICATION_HEADER = "[ICARUS ADJUDICATION: PASS]"
WORK_RECEIPT = "[WORK] EXECUTION RECEIPT"
EXECUTION_HEADER = "[ICARUS EXECUTION RECEIPT]"
VERIFICATION_HEADER = "[ICARUS INDEPENDENT VERIFICATION]"
TERMINAL_HEADER = "[ICARUS TERMINAL EVIDENCE]"
TERMINAL_CLOSED_HEADER = "[ICARUS TERMINAL CLOSED]"
ECHO_DIRECTIVE = "Echo test for task intake and worker delegation verification."
MONITOR_ONLY_MARKER = re.compile(
    r"^\s*(\[ICARUS SUPERVISORY DIRECTIVE\]|ICARUS_RUN)(?=\s|$)",
    re.IGNORECASE | re.MULTILINE,
)
TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
CHAIRS = {"[WORK]", "[CODEX]", "[SOL]", "[LUNA]", "[GRACE]"}
LEGACY_CHAIRS = {"[WORK]", "[SOL]"}
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
REPO_ROOT = Path(__file__).resolve().parents[2]


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
            pairs = [parse_field(line) for line in fields.splitlines()
                     if ":" in line and (header != DISPATCH_HEADER or line == line.lstrip())]
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


def load_agent_signers(raw):
    """Load enrolled raw Ed25519 public keys from trusted runner configuration."""
    config = json.loads(raw)
    if not isinstance(config, dict) or config.keys() != {"executors", "verifier"}:
        raise ValueError("Invalid ICARUS_DUTY_AGENT_SIGNERS fields")
    executors = config["executors"]
    if not isinstance(executors, dict) or not executors or not executors.keys() <= CHAIRS:
        raise ValueError("Invalid ICARUS_DUTY_AGENT_SIGNERS executors")
    signers = {**executors, VERIFICATION_HEADER: config["verifier"]}
    if any(not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", key)
           for key in signers.values()):
        raise ValueError("Invalid ICARUS_DUTY_AGENT_SIGNERS public key")
    signers = {role: bytes.fromhex(key) for role, key in signers.items()}
    if len(set(signers.values())) != len(signers):
        raise ValueError("ICARUS_DUTY_AGENT_SIGNERS requires distinct public keys")
    return signers


def agent_receipt_message(outbox_url, header, packet):
    """Canonical UTF-8 payload for an execution or independent verification signature."""
    return json.dumps({
        "domain": "icarus-duty-agent-receipt-v1",
        "outbox": outbox_url,
        "header": header,
        "fields": {key: value for key, value in packet.items() if key != "agent signature"},
    }, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def verifies_agent_receipt(outbox_url, header, packet, public_key):
    signature = packet.get("agent signature", "")
    if public_key is None or not re.fullmatch(r"[0-9a-f]{128}", signature):
        return False
    with tempfile.TemporaryDirectory(prefix="icarus-agent-receipt-") as directory:
        files = Path(directory)
        # RFC 8410 SubjectPublicKeyInfo for a raw Ed25519 public key.
        (files / "key.der").write_bytes(bytes.fromhex("302a300506032b6570032100") + public_key)
        (files / "receipt").write_bytes(agent_receipt_message(outbox_url, header, packet))
        (files / "signature").write_bytes(bytes.fromhex(signature))
        result = subprocess.run(
            ["openssl", "pkeyutl", "-verify", "-rawin", "-pubin", "-keyform", "DER",
             "-inkey", "key.der", "-in", "receipt", "-sigfile", "signature"],
            cwd=files, capture_output=True, timeout=5, check=False,
        )
        return result.returncode == 0


def verified_backlog_results(comments, verifier_id, agent_signers, outbox_url):
    workers = {comment["id"]: (comment, packet)
               for comment, packet in comment_packets(comments, EXECUTION_HEADER)}
    for comment, proof in comment_packets(comments, VERIFICATION_HEADER):
        verifier = comment.get("user") or {}
        if not unedited(comment):
            continue
        if not agent_signers and (
                str(verifier.get("id")) != verifier_id or verifier.get("type") != "Bot"
                or verifier.get("login") == "github-actions[bot]"):
            continue
        worker_id = proof.get("execution comment id", "")
        if not worker_id.isascii() or not worker_id.isdecimal() or len(worker_id) > 20:
            continue
        worker, execution = workers.get(int(worker_id), ({}, {}))
        worker_user = worker.get("user") or {}
        if (type(worker_user.get("id")) is not int or worker_user["id"] <= 0
                or (not agent_signers and str(worker_user["id"]) == verifier_id)
                or not unedited(worker)
                or worker["id"] >= comment["id"]
                or execution.get("task id") != proof["task id"]
                or execution.get("dispatch comment id") != proof.get("dispatch comment id")
                or execution.get("git commit sha") != proof.get("git commit sha")
                or not re.fullmatch(r"[0-9a-f]{40}", proof.get("git commit sha", ""))
                or proof.get("scope verified") != "true"
                or proof.get("incremental spend eur") != "0"):
            continue
        exit_code = proof.get("exit code", "")
        expected = proof.get("expected sha256", "")
        observed = proof.get("observed sha256", "")
        if (not re.fullmatch(r"-?[0-9]{1,10}", exit_code)
                or not re.fullmatch(r"[0-9a-f]{64}", expected)
                or (observed != "missing" and not re.fullmatch(r"[0-9a-f]{64}", observed))):
            continue
        fingerprints = {}
        if agent_signers:
            executor_key = agent_signers.get(execution.get("target chair"))
            verifier_key = agent_signers[VERIFICATION_HEADER]
            if (not verifies_agent_receipt(outbox_url, EXECUTION_HEADER, execution, executor_key)
                    or not verifies_agent_receipt(outbox_url, VERIFICATION_HEADER, proof, verifier_key)):
                continue
            fingerprints = {
                "executor_sha": hashlib.sha256(executor_key).hexdigest(),
                "verifier_sha": hashlib.sha256(verifier_key).hexdigest(),
            }
            if fingerprints["executor_sha"] == fingerprints["verifier_sha"]:
                continue
        yield comment, proof, execution, int(exit_code), expected, observed, fingerprints


def unedited(comment):
    created = comment.get("created_at")
    return bool(created and created == comment.get("updated_at"))


def post_and_read_comment(issues_url, outbox_url, token, body):
    comment_id = post_comment(outbox_url, token, body)
    comment, _ = call_github_api(f"{issues_url}/comments/{comment_id}", token)
    if (comment.get("id") != comment_id or comment.get("body") != body
            or comment.get("issue_url") != outbox_url.removesuffix("/comments")
            or (comment.get("user") or {}).get("login") != "github-actions[bot]"):
        raise RuntimeError(f"Terminal comment {comment_id} failed readback")
    return comment_id


def adjudicate_backlog(issues_url, mailbox, comments, dispatches, token, record):
    """Consume separate automated execution and verification receipts.

    A worker reports the source commit and dispatch ID under EXECUTION_HEADER.
    The verifier independently reports that pair, the execution comment ID,
    exit code, artifact SHA-256 values, scope and cost under VERIFICATION_HEADER.
    With enrolled signing keys, both roles sign and the GitHub account transports
    their receipts. Legacy deployments can still use an independent verifier bot.
    """
    raw_signers = os.getenv("ICARUS_DUTY_AGENT_SIGNERS", "")
    agent_signers = load_agent_signers(raw_signers) if raw_signers else None
    verifier_id = os.getenv("ICARUS_DUTY_VERIFIER_USER_ID", "")
    if not agent_signers and not verifier_id:
        return
    if not agent_signers and not re.fullmatch(r"[1-9][0-9]{0,19}", verifier_id):
        raise ValueError("Invalid ICARUS_DUTY_VERIFIER_USER_ID")

    active = {}
    for dispatch, packet in sorted(dispatches, key=lambda entry: entry[0]["id"]):
        task_id = packet["task id"]
        match = re.fullmatch(r"BACKLOG-([1-9][0-9]{0,9})", task_id)
        if (match and int(match[1]) != mailbox and packet.get("target chair") in CHAIRS
                and packet.get("directive") and packet.get("source file")
                and re.fullmatch(r"[0-9a-f]{40}", packet.get("source blob", ""))
                and re.fullmatch(rf"#{match[1]} \(comment [1-9][0-9]{{0,19}}\)",
                                 packet.get("source issue", ""))):
            active[task_id] = dispatch, packet, int(match[1])

    resolved = {
        (packet["task id"], packet.get("dispatch comment id"))
        for _, packet in comment_packets(comments, TERMINAL_CLOSED_HEADER, bot_only=True)
    }
    prepared = {
        (packet["task id"], packet.get("dispatch comment id")): comment
        for comment, packet in comment_packets(comments, TERMINAL_HEADER, bot_only=True)
    }
    outbox_url = f"{issues_url}/{mailbox}/comments"
    for verification, proof, execution, exit_code, expected, observed, fingerprints in verified_backlog_results(
            comments, verifier_id, agent_signers, outbox_url):
        task_id = proof["task id"]
        if task_id not in active:
            continue
        dispatch, packet, issue = active[task_id]
        dispatch_id = dispatch["id"]
        key = task_id, str(dispatch_id)
        if (key in resolved or proof.get("dispatch comment id") != key[1]
                or int(proof["execution comment id"]) <= dispatch_id
                or execution.get("target chair") != packet["target chair"]):
            continue

        source_url = f"{issues_url}/{issue}"
        current, _ = call_github_api(source_url, token)
        if current.get("number") != issue or "pull_request" in current:
            raise RuntimeError(f"Terminal issue #{issue} failed readback")
        claim_id = int(packet["source issue"].split("comment ")[1][:-1])
        claim, _ = call_github_api(f"{issues_url}/comments/{claim_id}", token)
        claim_body = next(comment_packets([claim], CLAIM_HEADER, bot_only=True), (None, {}))[1]
        if (claim_id >= dispatch_id or claim.get("id") != claim_id or claim.get("issue_url") != source_url
                or claim_body.get("task id") != task_id
                or claim_body.get("target chair") != packet["target chair"]):
            continue

        passed = exit_code == 0 and expected == observed
        verdict = "PASS" if passed else "FAIL"
        if current.get("state") != "open" and not (
                passed and key in prepared and current.get("state") == "closed"
                and current.get("state_reason") == "completed"):
            continue
        state = record["task_states"].setdefault(task_id, {})
        detail = {
            "task_id": task_id, "issue_number": issue, "dispatch_comment_id": dispatch_id,
            "verification_comment_id": verification["id"], "git_commit_sha": proof["git commit sha"],
            "exit_code": exit_code, "expected_sha256": expected, "observed_sha256": observed,
            "verdict": verdict,
            **fingerprints,
        }
        marker = (
            f"{TERMINAL_HEADER}\nTask ID: {task_id}\nDispatch Comment ID: {dispatch_id}\n"
            f"Verification Comment ID: {verification['id']}\nVerdict: {verdict}\n"
            f"Git Commit SHA: {proof['git commit sha']}\nExit Code: {exit_code}\n"
            f"Expected SHA256: {expected}\nObserved SHA256: {observed}"
        )
        if fingerprints:
            marker += (f"\nExecutor SHA: {fingerprints['executor_sha']}"
                       f"\nVerifier SHA: {fingerprints['verifier_sha']}")
        if key in prepared:
            prior = prepared[key]
            if prior.get("body") != marker:
                continue
            detail["adjudication_comment_id"] = prior["id"]
        else:
            detail["adjudication_comment_id"] = post_and_read_comment(
                issues_url, outbox_url, token, marker,
            )

        detail["status"] = "ADJUDICATED"
        record["terminal_receipts"].append(detail)
        if passed:
            if current["state"] == "open":
                call_github_api(source_url, token, "PATCH", {"state": "closed", "state_reason": "completed"})
            closed, _ = call_github_api(source_url, token)
            if (closed.get("number") != issue or closed.get("state") != "closed"
                    or closed.get("state_reason") != "completed"):
                raise RuntimeError(f"Terminal closure for issue #{issue} failed readback")
            detail["closure_comment_id"] = post_and_read_comment(
                issues_url, outbox_url, token,
                f"{TERMINAL_CLOSED_HEADER}\nTask ID: {task_id}\nDispatch Comment ID: {dispatch_id}\n"
                f"Adjudication Comment ID: {detail['adjudication_comment_id']}\nSource Issue: #{issue}",
            )
            state["status"] = "CLOSED"
        elif "reissue of" in packet:
            state.update(status="BLOCKED", terminal_blocker="REPAIR_LEASH_EXHAUSTED")
        elif not reissue_source_matches(packet):
            state.update(status="BLOCKED", terminal_blocker="DISPATCH_SOURCE_CHANGED")
        else:
            failure = f"process exited {exit_code}" if exit_code else "artifact digest mismatch"
            # Keep the original scope, source and chair. Only the failed
            # acceptance condition is tightened and the remaining leash is zero.
            first, separator, remainder = dispatch["body"].partition("\nBudget: ")
            reissue = (
                f"{first}\n    Repair constraint: Prior {failure}. Require exit code 0 and "
                f"independently verify expected artifact digest {expected}."
                f"{separator}{remainder.replace('Repair Leash: 1 attempt', 'Repair Leash: 0 attempts', 1)}"
                f"\nReissue Of: {dispatch_id}\nAdjudication Comment ID: {detail['adjudication_comment_id']}"
            )
            reissue_id = post_and_read_comment(issues_url, outbox_url, token, reissue)
            detail["reissue_comment_id"] = reissue_id
            state.update(status="WAITING_FOR_RECEIPT", dispatch_comment_id=reissue_id)
            record["dispatch_receipts"].append({
                "task_id": task_id, "issue_number": issue, "source_comment_id": claim_id,
                "delegated_to": packet["target chair"], "dispatch_comment_id": reissue_id,
            })
        resolved.add(key)
        detail["status"] = state["status"]
        if "terminal_blocker" in state:
            detail["blocker"] = state["terminal_blocker"]


def reissue_source_matches(packet):
    task_id = packet["task id"]
    task = task_id, packet["target chair"], packet["directive"], [packet["source file"]]
    states = {}
    return (preflight_source(task, {"task_states": states})
            and states[task_id]["source_blob"] == packet["source blob"])


def parse_task(fields):
    id_line, _, remainder = fields.lstrip().partition("\n")
    chair_line, _, scope_field = remainder.lstrip().partition("\n")
    id_label, task_id = parse_field(id_line)
    chair_label, chair = parse_field(chair_line)
    scope_line, _, remaining = scope_field.partition("\n")
    scope_label, scope = parse_field(scope_line)
    scope_lines = [scope]
    source_files = []
    for line in remaining.splitlines():
        label, value = parse_field(line)
        if label == "source file":
            source_files.append(value)
        else:
            scope_lines.append(line)
    scope = "\n".join(scope_lines).strip()
    if (
        id_label == "task id"
        and len(task_id.split()) == 1
        and chair_label == "target chair"
        and chair in CHAIRS
        and scope_label in {"scope", "scope instruction", "directive"}
        and scope
    ):
        return task_id, chair, scope, source_files
    return None


def preflight_source(task, record):
    task_id, chair, scope, source_files = task
    state = {"target_chair": chair}
    record["task_states"][task_id] = state
    if (not source_files and task_id.startswith("CANARY-INTAKE-")
            and chair == "[WORK]" and scope == ECHO_DIRECTIVE):
        state.update(status="PREFLIGHT_VERIFIED", source_preflight="ECHO_CANARY")
        return True

    error = "SOURCE_FILE_REQUIRED"
    if len(source_files) == 1 and source_files[0]:
        source = source_files[0]
        state["source_file"] = source
        if "\\" in source or "\0" in source or any(
                part in {"", ".", ".."} for part in source.split("/")):
            error = "INVALID_SOURCE_PATH"
        else:
            # Inspect the exact path in the trusted checkout. The mode check
            # excludes directories, symlinks and submodules.
            try:
                result = subprocess.run(
                    ["git", "--literal-pathspecs", "ls-tree", "-z", "--full-tree",
                     "HEAD", "--", source],
                    cwd=REPO_ROOT, capture_output=True, timeout=5, check=True,
                )
            except (OSError, subprocess.SubprocessError, ValueError):
                error = "SOURCE_CHECK_UNAVAILABLE"
            else:
                metadata, _, name = result.stdout.partition(b"\t")
                fields = metadata.split()
                if (len(fields) == 3 and fields[0] in {b"100644", b"100755"}
                        and fields[1] == b"blob" and name == os.fsencode(source) + b"\0"):
                    state.update(status="PREFLIGHT_VERIFIED", source_preflight="VERIFIED",
                                 source_blob=fields[2].decode("ascii"))
                    return True
                error = "SOURCE_FILE_NOT_TRACKED"
    elif len(source_files) > 1:
        error = "AMBIGUOUS_SOURCE_FILE"
    state.update(status="PREFLIGHT_BLOCKED", source_preflight=error)
    return False


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
    task_id, chair, scope, _ = task
    state = record["task_states"][task_id]
    scope = scope.replace("\n", "\n    ")
    body = (
        f"{DISPATCH_HEADER}\nTask ID: {task_id}\nTarget Chair: {chair}\n"
        f"Directive: {scope}\nBudget: €0.00 | Repair Leash: 1 attempt"
    )
    if "source_blob" in state:
        body += f"\nSource File: {state['source_file']}\nSource Blob: {state['source_blob']}"
    if origin["issue_number"] != mailbox:
        body += f"\nSource Issue: #{origin['issue_number']}"
        if origin["source_comment_id"] is not None:
            body += f" (comment {origin['source_comment_id']})"
    comment_id = post_comment(outbox_url, token, body)
    state.update(status="WAITING_FOR_RECEIPT", dispatch_comment_id=comment_id)
    record["dispatch_receipts"].append({
        **origin, "task_id": task_id, "delegated_to": chair, "dispatch_comment_id": comment_id,
    })


def run_pilot_if_approved(task_id, number, seat, policy, policy_digest, issues_url, outbox_url, token, record):
    spec = policy["approved_pilots"].get(task_id)
    if not spec or policy["verifier_user_id"] is None:
        return
    approvals = fetch_pages(f"{issues_url}/141/comments", token)
    now = datetime.datetime.now(datetime.timezone.utc)
    states, _ = pilot_state.availability(fetch_pages(outbox_url, token), policy["seat_reporters"], now)
    if (any(value != "unavailable" for value in states.values())
            or not pilot_state.owner_approved(approvals, task_id, policy_digest, now)):
        return
    reservation = pilot_state.reserve_attempt(task_id, outbox_url, token, fetch_pages, post_comment)
    if reservation is None:
        return
    record["pilot_attempt"] = {"task_id": task_id, "issue_number": number,
                               "reservation_comment_id": reservation,
                               "verifier_user_id": policy["verifier_user_id"],
                               "source_commit": os.environ["GITHUB_SHA"]}
    approvals = fetch_pages(f"{issues_url}/141/comments", token)
    current_reports = fetch_pages(outbox_url, token)
    now = datetime.datetime.now(datetime.timezone.utc)
    states, expiries = pilot_state.availability(current_reports, policy["seat_reporters"], now)
    if (any(value != "unavailable" for value in states.values())
            or not pilot_state.owner_approved(approvals, task_id, policy_digest, now)):
        record["pilot_attempt"]["blocked_before_execution"] = "Availability or owner approval changed after reservation"
        return
    record["pilot_attempt"].update(pilot_state.execute_readback(task_id, seat, states, min(expiries.values()), spec))
    record["loop_state"] = "WAITING_FOR_INDEPENDENT_VERIFIER"


def monitor_issues(repo, mailbox, token, record):
    issues_url = f"https://api.github.com/repos/{repo}/issues"
    outbox_url = f"{issues_url}/{mailbox}/comments"
    issues = fetch_pages(f"{issues_url}?state=open&sort=created&direction=asc", token)
    open_issues = {issue["number"]: issue for issue in issues if "pull_request" not in issue}
    outbox_comments = fetch_pages(outbox_url, token)
    policy, policy_digest = pilot_state.load_policy()
    reporters = policy["seat_reporters"]
    registry_ready = set(reporters) == pilot_state.SEATS
    dispatch_packets = [packet for _, packet in comment_packets(outbox_comments, DISPATCH_HEADER)]
    bot_dispatches = list(comment_packets(outbox_comments, DISPATCH_HEADER, bot_only=True))
    dispatched = {packet["task id"] for packet in dispatch_packets}
    dispatched_sources = {
        int(source[1]) for packet in dispatch_packets
        if (source := re.match(r"^#(\d+)(?:\s|$)", packet.get("source issue", "")))
    }
    pending = []
    candidates = []
    scheduled = os.environ.get("GITHUB_EVENT_NAME") == "schedule"
    live_schedule = pilot_state.on_live_schedule(repo)
    task_states = record["task_states"]
    for dispatch, packet in sorted(bot_dispatches, key=lambda entry: entry[0]["id"]):
        task_id = packet["task id"]
        backlog = re.fullmatch(r"BACKLOG-(\d+)", task_id)
        if backlog and int(backlog[1]) not in open_issues:
            continue
        state = task_states[task_id] = {
            "status": "WAITING_FOR_RECEIPT", "dispatch_comment_id": dispatch["id"],
            "target_chair": packet.get("target chair"),
        }
        if packet.get("source file") and packet.get("source blob"):
            state.update(source_preflight="VERIFIED", source_file=packet["source file"],
                         source_blob=packet["source blob"])
    for adjudication, packet in comment_packets(outbox_comments, ADJUDICATION_HEADER, bot_only=True):
        if packet["task id"] in task_states:
            task_states[packet["task id"]].update(
                status="ADJUDICATED", adjudication_comment_id=adjudication["id"],
            )

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
            if (task_id not in dispatched and number not in dispatched_sources
                    and not pilot_state.reserved(outbox_comments, task_id)
                    and (registry_ready or candidate[2] in LEGACY_CHAIRS)):
                claim = next((comment for comment, packet in comment_packets(comments, CLAIM_HEADER, bot_only=True)
                              if packet["task id"] == task_id
                              and packet.get("target chair") == candidate[2]), None)
                candidates.append((claim is None, candidate, claim))

    # Explicit operator work overrides automatic selection. Preserve existing packet routing.
    considered = set(dispatched)
    for origin, task in pending:
        task_id = task[0]
        if task_id in considered:
            record["duplicate_directives_ignored"] += 1
            continue
        considered.add(task_id)
        if not preflight_source(task, record):
            continue
        chair = task[1]
        seat = chair.strip("[]")
        if seat in pilot_state.SEATS and (registry_ready or chair not in LEGACY_CHAIRS):
            reports = fetch_pages(outbox_url, token)
            states, _ = pilot_state.availability(reports, reporters, datetime.datetime.now(datetime.timezone.utc))
            if states[seat] != "available":
                record["held_specialist_routes"].append({"task_id": task_id, "target_chair": chair,
                                                         "availability": states[seat]})
                continue
        dispatch_task(outbox_url, token, origin, task, mailbox, record)
        record["loop_state"] = "DISPATCHED"
    if not scheduled:
        return

    record["waiting_canary"] = adjudicate_canaries(
        repo, mailbox, outbox_comments, bot_dispatches, outbox_url, token, record,
    )
    adjudicate_backlog(issues_url, mailbox, outbox_comments, bot_dispatches, token, record)
    record["waiting_backlog"] = [
        {"task_id": task_id, "dispatch_comment_id": state["dispatch_comment_id"]}
        for task_id, state in task_states.items()
        if re.fullmatch(r"BACKLOG-[0-9]+", task_id) and state["status"] == "WAITING_FOR_RECEIPT"
    ]
    if record["adjudication_receipts"]:
        for receipt in record["adjudication_receipts"]:
            task_states[receipt["task_id"]].update(
                status="ADJUDICATED", adjudication_comment_id=receipt["adjudication_comment_id"],
            )
        record["loop_state"] = "ADJUDICATED"
        return
    if record["dispatch_receipts"]:
        return
    if record["terminal_receipts"]:
        record["loop_state"] = "ADJUDICATED"

    # Outstanding receipts are recorded above. Discovery already excludes their dispatched backlog tasks.
    # Resume a previously persisted claim first. The workflow serializes Pulse jobs.
    for _, candidate, claim in sorted(candidates, key=lambda item: (item[0], item[1])):
        _, number, chair, _ = candidate
        task_id = f"BACKLOG-{number}"
        if task_id in considered:
            continue
        current, _ = call_github_api(f"{issues_url}/{number}", token)
        fresh = backlog_candidate(current)
        if fresh != candidate:
            continue
        scope = f"{fresh[3]}. Read the canonical scope and evidence gates in https://github.com/{repo}/issues/{number}."
        sources = re.findall(r"^\[SOURCE_FILE\][ \t]*([^\r\n]*)", current.get("body") or "", re.I | re.M)
        task = (task_id, chair, scope, [source.strip() for source in sources])
        if not preflight_source(task, record):
            continue
        seat = chair.strip("[]")
        if seat in pilot_state.SEATS and registry_ready:
            reports = fetch_pages(outbox_url, token)
            states, _ = pilot_state.availability(reports, reporters, datetime.datetime.now(datetime.timezone.utc))
            if states[seat] != "available":
                record["held_specialist_routes"].append({"task_id": task_id, "target_chair": chair,
                                                         "availability": states[seat]})
                record["loop_state"] = "WAITING_FOR_SPECIALIST"
                if claim is None and live_schedule and all(value == "unavailable" for value in states.values()):
                    run_pilot_if_approved(task_id, number, seat, policy, policy_digest,
                                          issues_url, outbox_url, token, record)
                break
        claim_id = claim["id"] if claim else post_comment(f"{issues_url}/{number}/comments", token, (
            f"{CLAIM_HEADER}\nTask ID: {task_id}\nTarget Chair: {chair}\n"
            "Budget: €0.00 | Repair Leash: 1 attempt"
        ))
        record["backlog_claim"] = {"issue_number": number, "claim_comment_id": claim_id}
        task_states[task_id]["status"] = "CLAIMED"
        dispatch_task(outbox_url, token, {"issue_number": number, "source_comment_id": claim_id},
                      task, mailbox, record)
        record["loop_state"] = "DISPATCHED"
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
        "terminal_receipts": [],
        "waiting_canary": [],
        "waiting_backlog": [],
        "task_states": {},
        "backlog_claim": None,
        "held_specialist_routes": [],
        "pilot_attempt": None,
        "loop_state": "IDLE_SELECT",
        "first_processing_error": None,
    }
    # GitHub can start a scheduled run after its intended UTC slot.
    duty_schedule = os.environ.get("ICARUS_PULSE_DUTY_SCHEDULE")
    cadence_skip = (
        os.environ.get("GITHUB_EVENT_NAME") == "schedule"
        and (not duty_schedule or os.environ.get("ICARUS_PULSE_TRIGGER_SCHEDULE") != duty_schedule)
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
        if (not status["adjudication_receipts"] and not status["terminal_receipts"]
                and all(state["status"] in {"ADJUDICATED", "CLOSED"}
                        for state in status["task_states"].values())):
            # This is a receipt for the completed inspection only. Task
            # execution keeps its independent tool and evidence requirements.
            status["idle_receipt"] = {
                "verdict": "PASS", "reason": "NO_TASK_ACTION_REQUIRED",
                "required_task_tool_calls": 0, "exit_code": 0,
            }
    record = {**entry, **status}
    append_ledger(record)
    append_status(record)
    print(json.dumps(record), file=sys.stderr if failed else sys.stdout)
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
