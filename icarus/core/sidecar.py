"""Fail-closed, exact-head GitHub review gate for the dedicated Sidecar account."""

import base64
import datetime
import hashlib
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path

from dsh.state_write_gate import GitHub, LIMIT, REPOSITORY, REPOSITORY_ID, parse
from icarus.core.duty_runner import call_github_api, fetch_pages
from icarus.core.pilot_state import PULSE_ACTOR_ID, on_live_schedule, owner_approved


POLICY_PATH = Path(__file__).resolve().parents[1] / "runtime" / "sidecar-verifier.json"
LEDGER = "logs/RUN_LOG.jsonl"
CHAIRS = {"SOL", "CLAUDE", "CODEX"}
MIN_TESTS = 215
PULSE_WORKFLOW_ID = 410687420
TASK_ID = "TASK-SIDECAR-VERIFIER-ROTATION-01"


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def rotation(author_ids, chairs, sidecar_id):
    identities = [*chairs.values(), sidecar_id, PULSE_ACTOR_ID]
    require(set(chairs) == CHAIRS and all(type(i) is int and i > 0 for i in identities)
            and len(set(identities)) == len(identities), "Separate authenticated identities are required")
    require(bool(author_ids) and None not in author_ids and author_ids <= set(chairs.values()),
            "Every implementation author must be enrolled")
    verifier = "CLAUDE" if chairs["SOL"] in author_ids else "SOL"
    require(chairs[verifier] not in author_ids and sidecar_id not in author_ids,
            "Rotated verifier or Sidecar is an implementation author")
    return verifier, chairs[verifier]


def actor(row, field="user"):
    return (row.get(field) or {}).get("id")


def head_sha(pr):
    return pr["head"]["sha"]


def ledger_bytes(api, sha):
    result = api.get(f"/contents/{LEDGER}?ref={sha}")
    require(result.get("encoding") == "base64", "Ledger encoding unsupported")
    return base64.b64decode(result["content"])


def independent_receipt(api, head, commit, verifier_id, number):
    parents = commit.get("parents", [])
    require(len(parents) == 1 and [f["filename"] for f in commit.get("files", [])] == [LEDGER],
            "Head must be the verifier's single-purpose ledger commit")
    require(actor(commit, "author") == verifier_id and actor(commit, "committer") == verifier_id
            and commit["commit"]["verification"]["verified"] is True,
            "Receipt commit is not authenticated to the rotated verifier")
    source = parents[0]["sha"]
    earlier, latest = ledger_bytes(api, source), ledger_bytes(api, head)
    addition = latest[len(earlier):]
    require(latest.startswith(earlier) and addition.endswith(b"\n") and addition.count(b"\n") == 1,
            "Verifier receipt must append exactly one ledger row")
    receipt = parse(addition)
    require(receipt.get("record_type") == "sidecar_ci_verification" and receipt.get("pr_number") == number
            and receipt.get("source_commit") == source and receipt.get("verifier_user_id") == verifier_id
            and type(receipt.get("exit_code")) is int and receipt["exit_code"] == 0,
            "Independent exit-code receipt does not match this PR and source")
    return receipt


def physical_ci(api, receipt):
    run_id, artifact_id = receipt.get("harness_run_id"), receipt.get("artifact_id")
    require(all(type(i) is int and i > 0 for i in (run_id, artifact_id)), "Missing CI run or artifact ID")
    run = api.get(f"/actions/runs/{run_id}")
    require(run.get("id") == run_id and run.get("head_sha") == receipt["source_commit"]
            and run.get("workflow_id") == PULSE_WORKFLOW_ID and run.get("event") == "pull_request"
            and run.get("conclusion") == "success" and run.get("repository", {}).get("id") == REPOSITORY_ID
            and run.get("head_repository", {}).get("id") == REPOSITORY_ID,
            "CI run identity, source or outcome mismatch")
    metadata = api.get(f"/actions/artifacts/{artifact_id}")
    require(metadata.get("workflow_run", {}).get("id") == run_id
            and metadata.get("name") == f"harness-run-log-{run_id}-{run['run_attempt']}"
            and metadata.get("expired") is False, "CI artifact identity mismatch")
    raw = api.archive(artifact_id)
    digest = hashlib.sha256(raw).hexdigest()
    require(digest == receipt.get("artifact_sha256") and metadata.get("digest") == "sha256:" + digest,
            "CI artifact SHA-256 mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = [info for info in archive.infolist() if info.filename == "RUN_LOG.jsonl"]
        require(len(entries) == 1 and entries[0].file_size <= LIMIT, "Physical run ledger missing or oversized")
        row = parse(archive.read(entries[0]))
    summary = re.fullmatch(r"(\d+) passed(?:, \d+ subtests passed)? in [0-9.]+s", row.get("pytest_summary") or "")
    require(row.get("run_id") == str(run_id) and row.get("harness_outcome") == "success"
            and row.get("harness_status") == "PASS" and type(row.get("harness_exit_code")) is int
            and row["harness_exit_code"] == 0 and summary and int(summary[1]) >= MIN_TESTS
            and receipt.get("tests_passed") == int(summary[1]), "Physical test count or process exit code mismatch")
    return int(summary[1])


def review(number, token, chairs, sidecar_id, api):
    root = f"https://api.github.com/repos/{REPOSITORY}"
    url = f"{root}/pulls/{number}"
    pr, _ = call_github_api(url, token)
    require(pr.get("state") == "open" and not pr.get("draft") and pr["base"]["ref"] == "main"
            and pr["head"]["repo"]["id"] == REPOSITORY_ID, "PR is outside the approved review surface")
    head = head_sha(pr)
    commits = fetch_pages(url + "/commits", token)
    require(1 < pr.get("commits", 0) < 250 and len(commits) == pr["commits"]
            and commits[-1]["sha"] == head, "Incomplete PR commit ancestry")
    authors = {actor(pr), *(actor(c, "author") for c in commits[:-1]),
               *(actor(c, "committer") for c in commits[:-1])}
    verifier, verifier_id = rotation(authors, chairs, sidecar_id)
    commit = api.get(f"/commits/{head}")
    parents = commit.get("parents", [])
    require(commit.get("sha") == head and len(parents) == 1 and parents[0]["sha"] == commits[-2]["sha"],
            "Verifier receipt does not directly follow source")
    receipt = independent_receipt(api, head, commit, verifier_id, number)
    count = physical_ci(api, receipt)
    checked = api.get(f"/actions/workflows/{PULSE_WORKFLOW_ID}/runs?event=pull_request&head_sha={head}&status=success")
    require(any(run.get("head_sha") == head and run.get("conclusion") == "success"
                and run.get("event") == "pull_request" for run in checked.get("workflow_runs", [])),
            "Receipt head must also pass CI")
    reviews = fetch_pages(url + "/reviews", token)
    if any(actor(r) == sidecar_id and r.get("state") == "APPROVED" and r.get("commit_id") == head for r in reviews):
        return
    fresh, _ = call_github_api(url, token)
    require(head_sha(fresh) == head and fresh.get("state") == "open" and not fresh.get("draft"), "PR changed during verification")
    response, _ = call_github_api(url + "/reviews", token, "POST", {
        "commit_id": head, "event": "APPROVE",
        "body": f"Independent verifier {verifier} (GitHub ID {verifier_id}). "
                f"Docker CI run {receipt['harness_run_id']}, {count} tests, exit code 0. "
                f"Evidence receipt in `{LEDGER}` at `{head}`.",
    })
    require(actor(response) == sidecar_id and response.get("state") == "APPROVED"
            and response.get("commit_id") == head, "Review write needs separate readback")
    print(json.dumps({"pr_number": number, "commit_id": head, "review_id": response["id"],
                      "sidecar_user_id": sidecar_id, "verifier_user_id": verifier_id, "exit_code": 0}))


def main():
    require(on_live_schedule(REPOSITORY), "Sidecar requires the default-branch scheduled workflow")
    raw_policy = POLICY_PATH.read_bytes()
    policy = parse(raw_policy)
    require(set(policy) == {"chairs", "sidecar_user_id", "pull_requests"}, "Invalid Sidecar policy")
    ids = policy["pull_requests"]
    require(isinstance(ids, list) and all(type(n) is int and n > 0 for n in ids), "Invalid PR allowlist")
    if not ids:
        return 0
    token = os.environ.get("SIDECAR_VERIFIER_TOKEN")
    require(bool(token), "Dedicated Sidecar credential missing")
    identity, _ = call_github_api("https://api.github.com/user", token)
    sidecar_id = policy["sidecar_user_id"]
    require(type(sidecar_id) is int and sidecar_id == identity.get("id"), "Sidecar credential identity mismatch")
    approvals = fetch_pages(f"https://api.github.com/repos/{REPOSITORY}/issues/141/comments", token)
    require(owner_approved(approvals, TASK_ID, hashlib.sha256(raw_policy).hexdigest(),
                           datetime.datetime.now(datetime.timezone.utc)), "Gatekeeper Sidecar approval missing")
    for number in sorted(set(ids)):
        review(number, token, policy["chairs"], sidecar_id, GitHub(token))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        print(f"Sidecar blocked: {error}", file=sys.stderr)
        sys.exit(3)
