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
    ICARUS_HEARTBEAT_SECONDS  liveness beacon interval on the ledger branch (default: 1800; 0 = off)
    ICARUS_BUILD_SHA      source commit of this image, reported in the heartbeat (default: unknown)
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

from .gitledger import ClaimLost, GitLedger, GitLedgerError
from .reasoner import ReasonerError
from .runner import execute
from .identity import load_identity
from .relay import notice_body, post_notice
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
    if spec.get("require_command_output"):
        limits["require_command_output"] = True
        limits["note"] = ("Use only allowed_commands as argv[0]. The expected_files must be PRODUCED BY "
                          "RUNNING a command (e.g. write a script in 'files', then run it); a file you "
                          "type directly into 'files' does not count and fails verification.")
    else:
        limits["note"] = ("Use only allowed_commands as argv[0] (or no commands at all). Files listed in "
                          "'files' are written for you, so creating a file needs no command.")
    return {**job["task"], "limits": limits}


def _iso(t: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


class Heartbeat:
    """Liveness beacon written to icarus/ledger/heartbeat/<runner>.json on the ledger branch.

    Lets other agents see when the laptop runner is offline instead of guessing from an
    empty queue. It proves only that the loop was alive at `utc`; it is never job evidence.
    A failed push is retried on the next loop pass; a beacon error never stops the daemon."""

    def __init__(self, ledger: GitLedger, runner_id: str, interval: int, clock=time.time):
        self.ledger, self.runner_id, self.interval, self.clock = ledger, runner_id, interval, clock
        self.started = clock()
        self.last: float | None = None
        self.settled = 0
        self.last_status = "starting"

    def note(self, out: dict) -> None:
        self.last_status = out.get("status", "unknown")
        if "receipt" in out and out.get("status") != "claim_lost":
            self.settled += 1

    def due(self) -> bool:
        return self.interval > 0 and (self.last is None or self.clock() - self.last >= self.interval)

    def beat(self) -> bool | None:
        """None when not due; True when pushed; False when the push failed (retried next pass)."""
        if not self.due():
            return None
        now = self.clock()
        payload = {"utc": _iso(now), "started_utc": _iso(self.started),
                   "last_status": self.last_status, "jobs_settled_since_start": self.settled,
                   "interval_seconds": self.interval,
                   "build": os.environ.get("ICARUS_BUILD_SHA", "").strip() or "unknown",
                   "note": "liveness only; job evidence is icarus/ledger/state and run_log.jsonl"}
        try:
            ok = self.ledger.heartbeat(self.runner_id, payload)
        except GitLedgerError as e:
            log.warning("heartbeat: %s", e)
            ok = False
        if ok:
            self.last = now
        return ok


FINAL_STATUSES = ("done", "BLOCKER_DISCOVERED")


def early_notice(ledger: GitLedger, out: dict, poster=None) -> bool | None:
    """Post the verifier's final verdict to the job's source issue right after settle.

    None when not applicable (not final, disabled, or no source issue); True/False = posted."""
    if out.get("status") not in FINAL_STATUSES or "receipt" not in out:
        return None
    if os.environ.get("ICARUS_EARLY_RELAY", "1").strip() == "0":
        return None
    try:
        job = ledger.job(out["job"])
        issue = int(job.get("task", {}).get("source_issue") or 0)
    except (GitLedgerError, ValueError, TypeError):
        return None
    if issue <= 0:
        return None
    body = notice_body(out["job"], out["status"], out["receipt"],
                       int(job["state"].get("attempts", 0)), _iso(time.time()))
    poster = poster or post_notice
    return poster(os.environ.get("TARGET_REPO", "").strip(), os.environ.get("GH_TOKEN", "").strip(),
                  issue, body)


def cycle(ledger: GitLedger, reasoner, runner_id: str, work_dir: Path,
          lease_seconds: int = 21600) -> dict:
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
    reasoner = ModelSwitcher(pool, identity=lambda: load_identity(clone))
    lease = int(os.environ.get("ICARUS_LEASE_SECONDS", "21600"))
    work = Path(os.environ.get("ICARUS_WORK_DIR", "/tmp/icarus-work"))
    runner_id = os.environ.get("ICARUS_RUNNER_ID", "daemon")
    poll = int(os.environ.get("ICARUS_POLL_SECONDS", "60"))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    hb = Heartbeat(ledger, runner_id, 0 if a.once else int(os.environ.get("ICARUS_HEARTBEAT_SECONDS", "1800")))
    while True:
        try:
            out = cycle(ledger, reasoner, runner_id, work, lease)
            log.info(json.dumps({k: v for k, v in out.items() if k != "receipt"}
                                | ({"verdict": out["receipt"]["verdict"]} if "receipt" in out else {})))
        except OwnerAuthError as e:
            print(f"OWNER ASSISTANCE REQUIRED — replace the rejected model key in primitives.env\n"
                  f"Evidence: {e}", file=sys.stderr)
            return 3
        except GitLedgerError as e:
            log.warning("ledger: %s", e)
            out = {"status": "ledger_error"}
        posted = early_notice(ledger, out)
        if posted is not None:
            log.info(json.dumps({"status": "early_notice", "job": out.get("job"), "posted": posted}))
        hb.note(out)
        pushed = hb.beat()
        if pushed is not None:
            log.info(json.dumps({"status": "heartbeat", "pushed": pushed}))
        if a.once:
            return 0 if out["status"] in ("idle", "done", "queued", "claim_lost") else 1
        time.sleep(poll if out["status"] in ("idle", "ledger_error") else 1)


if __name__ == "__main__":
    sys.exit(main())
