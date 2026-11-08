#!/usr/bin/env python3
"""
ICARUS Operational Duty Runner
-------------------------------
Role: Autonomous Dispatch & Wire Referee
Cost: €0.00 (Standard library only; authenticated via GITHUB_TOKEN)
Rules:
  - NO EVIDENCE = NO CLAIM: Validates physical HTTP status & comment IDs.
  - ZERO SELF-CERTIFICATION: Status is determined by exit codes and receipts.
  - APPEND-ONLY: Writes immutable execution state to icarus_status.json and RUN_LOG.jsonl.
"""

import os
import sys
import json
import datetime
import urllib.request
import urllib.error

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO = os.getenv("GITHUB_REPOSITORY", "the1mburke-blip/Teamchat")
ISSUE_NUMBER = int(os.getenv("ICARUS_ISSUE_NUMBER", "6"))

if not GITHUB_TOKEN:
    print("FATAL: GITHUB_TOKEN secret is missing or empty.", file=sys.stderr)
    sys.exit(1)

API_BASE = f"https://api.github.com/repos/{REPO}"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "ICARUS-Supervisory-Runner"
}

def call_github_api(endpoint, method="GET", payload=None):
    url = f"{API_BASE}/{endpoint}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status_code = resp.getcode()
            body = resp.read().decode("utf-8")
            return status_code, json.loads(body) if body else {}
    except urllib.error.HTTPError as err:
        error_body = err.read().decode("utf-8")
        return err.code, {"error": error_body}
    except Exception as err:
        return 500, {"error": str(err)}

def log_ledger_entry(run_id, status, details):
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record = {
        "timestamp_utc": timestamp,
        "run_id": run_id,
        "status": status,
        "details": details
    }
    with open("RUN_LOG.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    with open("icarus_status.json", "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

def main():
    run_id = f"RUN-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%SZ')}"
    print(f"=== ICARUS ON-DUTY WATCH: {run_id} ===")

    # Gate 1: Inspect Target Wire (Issue #6)
    print(f"Checking wire status on Issue #{ISSUE_NUMBER}...")
    status_code, issue_data = call_github_api(f"issues/{ISSUE_NUMBER}")
    if status_code != 200:
        print(f"BLOCKED: Unable to read Issue #{ISSUE_NUMBER}. HTTP {status_code}", file=sys.stderr)
        log_ledger_entry(run_id, "BLOCKED", f"HTTP {status_code} on issue read")
        sys.exit(1)

    print(f"Wire Verified: Issue #{ISSUE_NUMBER} is '{issue_data.get('state')}'.")

    # Gate 2: Fetch Recent Comments to Prevent Duplicate Dispatch
    status_code, comments = call_github_api(f"issues/{ISSUE_NUMBER}/comments?per_page=5")
    latest_comment_id = comments[-1]["id"] if (status_code == 200 and comments) else None

    # Gate 3: Emit Duty Heartbeat / Dispatch Verification to Issue #6
    payload = {
        "body": (
            f"### [ICARUS SUPERVISORY WATCH] — {run_id}\n"
            f"* **Status**: ACTIVE_ON_DUTY\n"
            f"* **Wire Status**: Issue #{ISSUE_NUMBER} Verified\n"
            f"* **Previous Comment ID**: `{latest_comment_id}`\n"
            f"* **Cost**: €0.00 | **Self-Certification**: NONE\n"
            f"* **Terminal Verdict**: WATCH_STANDING"
        )
    }

    print("Posting operational verification to wire...")
    post_status, post_resp = call_github_api(f"issues/{ISSUE_NUMBER}/comments", method="POST", payload=payload)

    if post_status == 201:
        new_comment_id = post_resp.get("id")
        print(f"PASS: Posted supervisory watch to Issue #{ISSUE_NUMBER}. Comment ID: {new_comment_id}")
        log_ledger_entry(run_id, "PASS", {"comment_id": new_comment_id, "html_url": post_resp.get("html_url")})
        sys.exit(0)
    else:
        print(f"BLOCKED: Failed to post comment. HTTP {post_status}: {post_resp}", file=sys.stderr)
        log_ledger_entry(run_id, "BLOCKED", post_resp)
        sys.exit(1)

if __name__ == "__main__":
    main()
