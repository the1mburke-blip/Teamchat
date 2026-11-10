"""Verify a deployed Pulse harness writeback with an authenticated read token.

Run from the repository root: python -m scripts.verify_icarus_pulse RUN_ID MERGE_SHA
Provide GITHUB_TOKEN with Actions and Issues read access.
"""

import argparse
from datetime import datetime, timedelta
import io
import json
import os
import sys
import zipfile

from dsh.state_write_gate import COMMIT, GitHub, LIMIT, REPOSITORY, REPOSITORY_ID, digest, parse, require


WORKFLOW = ".github/workflows/icarus-pulse.yml"
ISSUE = 6


def read_ledger(api, artifacts, run_id, name):
    matching = [item for item in artifacts if item.get("name") == name]
    require(len(matching) == 1, f"Expected exactly one artifact named {name}")
    artifact = matching[0]
    artifact_id = artifact.get("id")
    require(type(artifact_id) is int and artifact_id > 0 and artifact.get("expired") is False
            and artifact.get("workflow_run", {}).get("id") == run_id, "Artifact is unavailable or from another run")
    raw = api.archive(artifact_id)
    checksum = digest(raw)
    require(artifact.get("digest") == "sha256:" + checksum, "Artifact SHA-256 mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = [item for item in archive.infolist() if item.filename == "RUN_LOG.jsonl"]
        require(len(entries) == 1 and entries[0].file_size <= LIMIT, "Expected one bounded RUN_LOG.jsonl")
        ledger = archive.read(entries[0])
    return ledger, {"id": artifact_id, "sha256": checksum}


def verify(api, run_id, merge_sha):
    require(type(run_id) is int and run_id > 0 and COMMIT.fullmatch(merge_sha), "Invalid run ID or merge SHA")
    run = api.get(f"/actions/runs/{run_id}")
    require(run.get("id") == run_id and run.get("path") == WORKFLOW and run.get("head_sha") == merge_sha
            and run.get("head_branch") == "main" and run.get("event") == "push"
            and run.get("repository", {}).get("id") == REPOSITORY_ID
            and run.get("head_repository", {}).get("id") == REPOSITORY_ID
            and run.get("status") == "completed" and run.get("conclusion") == "success",
            "Expected a successful Teamchat main push of the specified commit")
    attempt = run.get("run_attempt")
    require(type(attempt) is int and attempt > 0, "Invalid writeback attempt")
    listing = api.get(f"/actions/runs/{run_id}/artifacts?per_page=100")
    require(listing.get("total_count", 101) <= 100, "Artifact listing incomplete")
    artifacts = listing["artifacts"]

    ledger, writeback_artifact = read_ledger(api, artifacts, run_id, f"harness-mailbox-log-{run_id}-{attempt}")
    lines = ledger.splitlines(keepends=True)
    require(len(lines) == 2, "Expected a physical ledger row and its writeback row")
    physical, receipt = map(parse, lines)
    require(isinstance(physical, dict) and isinstance(receipt, dict), "Invalid ledger rows")
    source_attempt = int(physical["run_attempt"])
    require(physical["run_attempt"] == str(source_attempt) and 0 < source_attempt <= attempt,
            "Invalid harness attempt")
    source_ledger, harness_artifact = read_ledger(api, artifacts, run_id, f"harness-run-log-{run_id}-{source_attempt}")
    require(source_ledger == lines[0], "Writeback ledger differs from the physical harness ledger")
    require(physical.get("run_id") == str(run_id) and physical.get("sha") == merge_sha
            and physical.get("event") == "push" and physical.get("ref") == "refs/heads/main"
            and physical.get("build_outcome") == physical.get("harness_outcome") == "success"
            and physical.get("harness_status") == "PASS"
            and type(physical.get("harness_exit_code")) is int and physical["harness_exit_code"] == 0,
            "Physical harness execution did not prove exit code 0")

    timestamp = datetime.fromisoformat(physical["timestamp"])
    require(timestamp.utcoffset() == timedelta(0), "Expected a UTC harness timestamp")
    comment_id = receipt.get("comment_id")
    require(receipt.get("record_type") == "harness_mailbox_writeback" and receipt.get("run_id") == str(run_id)
            and receipt.get("run_attempt") == physical["run_attempt"] and receipt.get("source_commit") == merge_sha
            and receipt.get("timestamp") == timestamp.isoformat() and receipt.get("status") == "PASSED"
            and type(receipt.get("harness_exit_code")) is int and receipt["harness_exit_code"] == 0
            and receipt.get("disposition") == "created" and receipt.get("http_status") == 201
            and type(comment_id) is int and comment_id > 0, "Writeback ledger does not prove HTTP 201")

    comment = api.get(f"/issues/comments/{comment_id}")
    issue_url = f"https://api.github.com/repos/{REPOSITORY}/issues/{ISSUE}"
    comment_url = f"https://github.com/{REPOSITORY}/issues/{ISSUE}#issuecomment-{comment_id}"
    expected_body = (
        "[ICARUS HARNESS EVIDENCE]\n"
        f"Run: https://github.com/{REPOSITORY}/actions/runs/{run_id}\n"
        f"Attempt: {source_attempt}\nSource Commit: {merge_sha}\nTimestamp: {timestamp.isoformat()}\n"
        "Harness Exit Code: 0\nStatus: PASSED"
    )
    require(comment.get("id") == comment_id and (comment.get("user") or {}).get("id") == 41898282
            and str(comment.get("issue_url", "")).casefold() == issue_url.casefold()
            and comment.get("html_url") == receipt.get("comment_url") == comment_url
            and bool(comment.get("created_at")) and comment["created_at"] == comment.get("updated_at")
            and comment.get("body") == expected_body, "Issue 6 comment did not match the writeback evidence")

    return {"record_type": "pulse_harness_writeback_verification", "repository": REPOSITORY,
            "workflow": WORKFLOW, "run_id": run_id, "writeback_attempt": attempt, "source_commit": merge_sha,
            "harness_timestamp": timestamp.isoformat(), "harness_exit_code": 0, "http_status": 201,
            "issue_number": ISSUE, "comment_id": comment_id, "comment_url": comment_url,
            "harness_artifact": harness_artifact, "writeback_artifact": writeback_artifact}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", type=int)
    parser.add_argument("merge_sha")
    args = parser.parse_args()
    try:
        result = verify(GitHub(os.getenv("GITHUB_TOKEN")), args.run_id, args.merge_sha)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        print(f"Pulse writeback verification failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
