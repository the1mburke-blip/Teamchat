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
    ICARUS_LEASE_SECONDS  claim lease (default: 21600 = 6 h; model rotation can run long)
    ICARUS_HOST           "any" (laptop, default) or "cloud": cloud skips laptop-only jobs
    ICARUS_MAX_POOL_BREAKS  give up after N full pool exhaustions (default 0 = never);
                          the cloud worker sets this so a job ends well inside its lease
    ICARUS_SANDBOX        "docker": each planned command runs in a no-network container
    GEMINI_API_KEY        Google models (AI Plus subscription) for the model switcher
    OPENROUTER_API_KEY    optional; OpenRouter :free routes join the pool when set
    Pool order/eligibility: <clone>/icarus/runtime/approved-routes.json (see switcher.py)

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

from .gitledger import BLOCKED, ClaimLost, GitLedger, GitLedgerError
from .reasoner import ReasonerError
from .runner import execute
from .identity import load_identity
from .switcher import ModelSwitcher, OwnerAuthError, load_pool
from .verify import verify

log = logging.getLogger("icarus.daemon")


def model_task(job: dict) -> dict:
    """What the model sees: the task plus the job's hard limits, so it plans inside them.
    Pass criteria stay with the verifier (hashes/forbidden patterns are not shown)."""
    spec = job["verify_spec"]
    limits = {"expected_files": spec.get("expected_files", [])}
    if spec.get("allowed_commands") is not None:
        limits["allowed_commands"] = spec["allowed_commands"]
    limits["note"] = ("Use only allowed_commands as argv[0] (or no commands at all). Files listed in "
                      "'files' are written for you, so creating a file needs no command.")
    return {**job["task"], "limits": limits}


def cycle(ledger: GitLedger, reasoner, runner_id: str, work_dir: Path,
          lease_seconds: int = 21600, host: str = "any") -> dict:
    try:
        job = ledger.claim(runner_id, lease_seconds, host=host)
    except ClaimLost as e:
        return {"status": "claim_lost", "job": str(e)}
    if job is None:
        return {"status": "idle"}
    attempt = job["state"]["attempts"] + 1
    job_dir = work_dir / job["id"] / f"attempt-{attempt}"
    job_dir.mkdir(parents=True, exist_ok=True)
    try:
        plan, plan_error = reasoner.plan(model_task(job)), None
    except OwnerAuthError:
        raise  # owner-only boundary: leave the job claimed-and-expiring, stop the daemon
    except ReasonerError as e:
        plan, plan_error = None, str(e)
    record = execute(job, plan, job_dir)
    if plan_error:
        record["error"] = plan_error
    receipt = verify(job_dir, job["verify_spec"], record, task_id=job["id"])
    receipt["models"] = list(getattr(reasoner, "trace", []))
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
    ap.add_argument("--drain", type=int, default=0, metavar="N",
                    help="run up to N cycles, stop early when idle (cloud worker)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    clone = os.environ.get("ICARUS_LEDGER_CLONE", "").strip()
    if not clone or not (Path(clone) / ".git").exists():
        print("OWNER ASSISTANCE REQUIRED — set ICARUS_LEDGER_CLONE to a dedicated git clone\n"
              "Evidence: ICARUS_LEDGER_CLONE unset or not a git clone", file=sys.stderr)
        return 3
    ledger = GitLedger(clone, os.environ.get("ICARUS_LEDGER_BRANCH", "main"))
    try:
        ledger.sync()
        pool = load_pool(Path(clone) / "icarus/runtime/approved-routes.json",
                         os.environ.get("GEMINI_API_KEY", "").strip(),
                         os.environ.get("OPENROUTER_API_KEY", "").strip())
    except (ReasonerError, GitLedgerError, OSError, ValueError) as e:
        print(f"OWNER ASSISTANCE REQUIRED — set GEMINI_API_KEY for the model switcher\n"
              f"Evidence: {e}", file=sys.stderr)
        return 3
    reasoner = ModelSwitcher(pool, identity=lambda: load_identity(clone),
                             max_pool_breaks=int(os.environ.get("ICARUS_MAX_POOL_BREAKS", "0")))
    host = os.environ.get("ICARUS_HOST", "any").strip() or "any"
    cycles = 0
    lease = int(os.environ.get("ICARUS_LEASE_SECONDS", "21600"))
    work = Path(os.environ.get("ICARUS_WORK_DIR", "/tmp/icarus-work"))
    runner_id = os.environ.get("ICARUS_RUNNER_ID", "daemon")
    poll = int(os.environ.get("ICARUS_POLL_SECONDS", "60"))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    while True:
        try:
            out = cycle(ledger, reasoner, runner_id, work, lease, host)
            cycles += 1
            log.info(json.dumps({k: v for k, v in out.items() if k != "receipt"}
                                | ({"verdict": out["receipt"]["verdict"]} if "receipt" in out else {})))
        except OwnerAuthError as e:
            print(f"OWNER ASSISTANCE REQUIRED — replace the rejected model key in primitives.env\n"
                  f"Evidence: {e}", file=sys.stderr)
            return 3
        except GitLedgerError as e:
            log.warning("ledger: %s", e)
            out = {"status": "ledger_error"}
        ok = out["status"] in ("idle", "done", "queued", "claim_lost", BLOCKED)
        if a.once:
            return 0 if ok else 1
        if a.drain:
            if out["status"] in ("idle", "ledger_error") or cycles >= a.drain:
                return 0 if ok else 1
            continue
        time.sleep(poll if out["status"] in ("idle", "ledger_error") else 1)


if __name__ == "__main__":
    sys.exit(main())
