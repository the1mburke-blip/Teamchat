#!/usr/bin/env python3
"""ICARUS pilot: dispatches staged packets from task_queue/ through the v3 harness.

For each task_queue/*.json, in name order:
  1. run harness-runner-v3.py's execute_packet() (dual gate, receipt to RUN_LOG.jsonl)
  2. archive the packet to processed/<stem>__<run_id>__<STATUS>.json
     (archived whatever the outcome, so no packet is ever blindly re-run)

Exit 0 when the queue is empty or every packet PASSed. Exit 1 otherwise.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
QUEUE = REPO / "task_queue"
PROCESSED = REPO / "processed"


def load_harness():
    spec = importlib.util.spec_from_file_location("harness_runner_v3", REPO / "harness-runner-v3.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    harness = load_harness()
    packets = sorted(p for p in QUEUE.glob("*.json") if p.is_file())
    if not packets:
        print(json.dumps({"state": "LISTENING", "queue": str(QUEUE.relative_to(REPO)), "packets": 0}))
        return 0
    PROCESSED.mkdir(exist_ok=True)
    summary, all_pass = [], True
    for packet in packets:
        result = harness.execute_packet(packet)
        r = result["receipt"]
        dest = PROCESSED / f"{packet.stem}__{r['run_id']}__{r['status']}.json"
        shutil.move(str(packet), dest)
        all_pass &= r["status"] == "PASS"
        summary.append({
            "packet": packet.name, "archived_to": str(dest.relative_to(REPO)),
            "run_id": r["run_id"], "task_id": r["task_id"], "status": r["status"],
            "git_sha": r["git_sha"], "receipt_hash": r["receipt_hash"],
            "gate_1": r["gate_1_technical"], "gate_2": r["gate_2_policy"],
            "readback": result["readback"], "issue_comment": result["issue_comment"],
        })
    ledger = harness.verify_ledger()
    print(json.dumps({"state": "PROCESSED", "results": summary, "ledger_verify": ledger}, indent=2))
    return 0 if all_pass and ledger["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
