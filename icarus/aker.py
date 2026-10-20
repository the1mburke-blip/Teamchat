"""Icarus Aker - primary autonomous repository runner.

Aker owns the cloud side of the shared lease and runs the existing managed
GOAL.md completion loop (dsh.completion) as owner "cloud". It adds no second
executor: kernel checks, tests, lease fencing and publication stay in dsh.

The receipt status is derived from observed outcomes only. Aker never writes
HANDOFF_READY and never self-certifies PASS; PASS is reserved for independent
adjudication (Icarus/Michael) against Actions run IDs and repository readback.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys

VERSION = "2.0.0-aker"
STATUS_FILE = os.path.join("icarus", "runs", "aker_status.json")
# Statuses Aker may emit. PASS and HANDOFF_READY are deliberately absent.
EMITTABLE = {"IDLE", "EXECUTING", "VERIFYING", "YIELDED", "BLOCKED", "FAIL"}
EXIT_OK = {"IDLE", "EXECUTING", "VERIFYING", "YIELDED"}


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pending_count(root="."):
    """Number of unfinished managed tasks in GOAL.md (uses dsh's own parser)."""
    root = os.path.abspath(root)
    if root not in sys.path:
        sys.path.insert(0, root)
    from dsh.completion import parse_goal

    with open(os.path.join(root, "GOAL.md"), encoding="utf-8") as handle:
        return sum(1 for task in parse_goal(handle.read()) if not task.done)


def head_sha(root="."):
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                            text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def run_loop(root=".", max_tasks=10, timeout=2400):
    """Run the managed completion loop as the cloud owner; return (rc, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, "-m", "dsh.completion", "--owner", "cloud", "--mode", "goals",
         "--max-tasks", str(max_tasks)],
        cwd=root, capture_output=True, text=True, timeout=timeout, check=False)
    return result.returncode, result.stdout, result.stderr


def classify(rc, stdout, before, after, head_before, head_after):
    """Map observed outcomes to (status, details). Pure function, no I/O."""
    progressed = after < before and head_before != head_after
    details = {"pending_before": before, "pending_after": after,
               "head_before": head_before, "head_after": head_after, "exit_code": rc}
    if before == 0:
        return "IDLE", {**details, "message": "No pending managed tasks."}
    if rc not in (0, 2):
        return "FAIL", {**details, "message": "Completion loop failed; see job log."}
    if "[ICARUS YIELD]" in stdout:
        return "YIELDED", {**details, "message": "Another worker holds a live lease; no task executed."}
    if rc == 2:
        if progressed:
            return "EXECUTING", {**details, "message": "Task limit reached; managed work remains."}
        return "BLOCKED", {**details, "message": "Task limit reached with no verified progress."}
    if progressed:
        return "VERIFYING", {**details,
                             "message": "Tasks completed and published; awaiting independent readback."}
    return "FAIL", {**details, "message": "Loop exited cleanly but no task completion was observed."}


def write_receipt(status, details, path=STATUS_FILE):
    if status not in EMITTABLE:
        raise ValueError(f"Aker may not emit status {status!r}")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    record = {"timestamp": _now(), "status": status, "details": details, "version": VERSION,
              "run_id": os.environ.get("GITHUB_RUN_ID", "local")}
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)
    print(f"[AKER] status={status} run_id={record['run_id']}")
    return record


def main(argv=None, *, count=pending_count, head=head_sha, loop=run_loop):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--max-tasks", type=int, default=10)
    parser.add_argument("--receipt", default=STATUS_FILE)
    args = parser.parse_args(argv)
    try:
        before = count(args.root)
        head_before = head(args.root)
        if before == 0:
            rc, out = 0, ""
        else:
            rc, out, err = loop(args.root, args.max_tasks)
            sys.stdout.write(out)
            sys.stderr.write(err)
        after = count(args.root)
        status, details = classify(rc, out, before, after, head_before, head(args.root))
    except Exception as error:  # noqa: BLE001 - receipt must record any failure
        status, details = "FAIL", {"message": f"{type(error).__name__}: {error}"}
    write_receipt(status, details, args.receipt)
    return 0 if status in EXIT_OK else 1


if __name__ == "__main__":
    sys.exit(main())
