"""Icarus daemon executor: the container half of the system.

The Apps Script pulse handles intake and decisions and queues code jobs into
icarus/ledger/queue/. This daemon claims one job at a time, plans it with the
reasoner, executes it in a confined work dir, has the verifier (incl. the repo's
existing icarus/harness/runner.py gate) grade it, and records the receipt in
the git ledger. It never grades its own work and never posts PASS itself.

Env:
    ICARUS_LEDGER_CLONE   dedicated git clone of the repo (hard-reset each cycle)
    ICARUS_LEDGER_BRANCH  branch holding icarus/ledger/ (default: main)
    ICARUS_WORK_DIR       where job attempts run (default: /tmp/icarus-work)
    ICARUS_RUNNER_ID      name in claims/receipts (default: daemon)
    ICARUS_POLL_SECONDS   idle sleep (default: 60)
    ICARUS_REASONER_URL / _MODEL / _KEY   see reasoner.py

Run:  python3 -m icarus.primitives.daemon            (loop)
      python3 -m icarus.primitives.daemon --once     (one cycle, then exit)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

from .gitledger import ClaimLost, GitLedger, GitLedgerError
from .reasoner import OpenAICompatReasoner, ReasonerError
from .runner import execute
from .verify import verify

log = logging.getLogger("icarus.daemon")


def cycle(ledger: GitLedger, reasoner, runner_id: str, work_dir: Path,
          lease_seconds: int = 900) -> dict:
    try:
        job = ledger.claim(runner_id, lease_seconds)
    except ClaimLost as e:
        return {"status": "claim_lost", "job": str(e)}
    if job is None:
        return {"status": "idle"}
    attempt = job["state"]["attempts"] + 1
    job_dir = work_dir / job["id"] / f"attempt-{attempt}"
    job_dir.mkdir(parents=True, exist_ok=True)
    try:
        plan, plan_error = reasoner.plan(job["task"]), None
    except ReasonerError as e:
        plan, plan_error = None, str(e)
    record = execute(job, plan, job_dir)
    if plan_error:
        record["error"] = plan_error
    receipt = verify(job_dir, job["verify_spec"], record, task_id=job["id"])
    receipt["ledger_head_at_claim"] = ledger.head()
    (job_dir / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    try:
        status = ledger.settle(job["id"], runner_id, receipt)
    except ClaimLost:
        return {"status": "claim_lost", "job": job["id"], "receipt": receipt}
    return {"status": status, "job": job["id"], "receipt": receipt}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Icarus daemon executor")
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    clone = os.environ.get("ICARUS_LEDGER_CLONE", "").strip()
    if not clone or not (Path(clone) / ".git").exists():
        print("OWNER ASSISTANCE REQUIRED — set ICARUS_LEDGER_CLONE to a dedicated git clone\n"
              "Evidence: ICARUS_LEDGER_CLONE unset or not a git clone", file=sys.stderr)
        return 3
    try:
        reasoner = OpenAICompatReasoner()
    except ReasonerError as e:
        print(f"OWNER ASSISTANCE REQUIRED — set ICARUS_REASONER_URL and ICARUS_REASONER_MODEL\n"
              f"Evidence: {e}", file=sys.stderr)
        return 3
    ledger = GitLedger(clone, os.environ.get("ICARUS_LEDGER_BRANCH", "main"))
    work = Path(os.environ.get("ICARUS_WORK_DIR", "/tmp/icarus-work"))
    runner_id = os.environ.get("ICARUS_RUNNER_ID", "daemon")
    poll = int(os.environ.get("ICARUS_POLL_SECONDS", "60"))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    while True:
        try:
            out = cycle(ledger, reasoner, runner_id, work)
            log.info(json.dumps({k: v for k, v in out.items() if k != "receipt"}
                                | ({"verdict": out["receipt"]["verdict"]} if "receipt" in out else {})))
        except GitLedgerError as e:
            log.warning("ledger: %s", e)
            out = {"status": "ledger_error"}
        if a.once:
            return 0 if out["status"] in ("idle", "done", "queued", "claim_lost") else 1
        time.sleep(poll if out["status"] in ("idle", "ledger_error") else 1)


if __name__ == "__main__":
    sys.exit(main())
