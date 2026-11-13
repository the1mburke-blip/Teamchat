#!/usr/bin/env python3
"""Build the Teamchat Issue #6 receipt comment from the last ledger line. Prints Markdown to stdout.

Usage: python3 receipt_comment.py [--ledger PATH] [--signed true|false] [--attestation-url URL] [--run-url URL]
The comment says SIGNED only when --signed true AND an attestation URL is given. Otherwise it says
hash-chained only. It never claims independent adjudication: the verifier here is Tier 1 machine.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def last_receipt(ledger: Path) -> dict:
    lines = [l for l in ledger.read_text("utf-8").splitlines() if l.strip()] if ledger.exists() else []
    if not lines:
        raise SystemExit("ledger is empty or missing; nothing to report")
    return json.loads(lines[-1])


def build_body(r: dict, signed: bool, attestation_url: str, run_url: str) -> str:
    g1, g2 = r["gate_1_technical"], r["gate_2_policy"]
    if signed and attestation_url:
        sig = f"SIGNED: yes, GitHub keyless artifact attestation (Sigstore) over RUN_LOG.jsonl: {attestation_url}"
    else:
        sig = "SIGNED: no (hash-chained only)"
    arts = "".join(f"\n- `{a['path']}` sha256 `{a['sha256']}`" for a in r.get("artifacts", [])) or "\n- none"
    return (
        f"[HARNESS-V3] {r['finished_at']}\n"
        f"STATUS: {r['status']} (Tier 1 machine gate; NOT independently adjudicated)\n"
        f"TASK: TASK-INIT-END-TO-END-CLOSED-LOOP-001 (issue #216), canary task {r['task_id']}\n"
        f"RUN_ID: {r['run_id']}\n"
        f"GATE_1: {g1['passed']} (exit_code_zero={g1['exit_code_zero']}, outputs={g1['physical_output_files_exist']}, "
        f"git_sha_logged={g1['git_sha_logged']})\n"
        f"GATE_2: {g2['passed']} (schema_valid={g2['schema_valid']}, zero_secrets={g2['zero_secrets_detected']}, "
        f"negative_constraints_met={g2['negative_constraints_met']})\n"
        f"GIT_SHA: {r['git_sha']}\n"
        f"receipt_hash={r['receipt_hash']}\n"
        f"{sig}\n"
        f"WORKFLOW_RUN: {run_url or 'n/a'}\n"
        f"ARTIFACTS:{arts}\n"
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=str(HERE / "icarus/runs/RUN_LOG.jsonl"))
    ap.add_argument("--signed", default="false")
    ap.add_argument("--attestation-url", default="")
    ap.add_argument("--run-url", default="")
    a = ap.parse_args(argv)
    sys.stdout.write(build_body(last_receipt(Path(a.ledger)), a.signed.lower() == "true", a.attestation_url, a.run_url))
    return 0


if __name__ == "__main__":
    sys.exit(main())
