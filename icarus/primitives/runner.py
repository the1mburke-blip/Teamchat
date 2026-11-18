"""Primitive 2 - Platform-Agnostic Execution Engine.

One linear cycle per invocation, then exit:
    Wake -> Read State -> Claim 1 Job -> Plan (reasoner) -> Execute
         -> Verify (independent referee) -> Write Evidence -> Exit

Schedule with anything that can start a process (cron, systemd timer,
Task Scheduler, a phone automation):

    0 * * * *  cd /path/to/Teamchat && python3 -m icarus.primitives.runner \
                 --root icarus/primitives/state --runner-id laptop

Safety:
- commands run as argv lists (no shell), cwd = jobs/<id>/, timeout each;
- file writes are confined to jobs/<id>/ (no absolute paths, no '..');
- allowed_commands in the verify_spec is enforced BEFORE execution
  (negative-constraint veto, template rule 6) and re-checked by the verifier.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from .ledger import Ledger
from .reasoner import OpenAICompatReasoner, ReasonerError
from .verify import verify

CMD_TIMEOUT = 300
DEFAULT_SANDBOX_IMAGE = "python:3.12-slim"


def _child_env(job_dir: Path) -> dict:
    """Model-planned commands never inherit the daemon's environment (tokens, keys)."""
    return {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(job_dir), "LANG": "C.UTF-8"}


def _sandboxed(argv: list[str], job_dir: Path) -> tuple[list[str], Path | None]:
    """ICARUS_SANDBOX=docker: run the command in a throwaway container with no network,
    no credentials, a read-only root and only the job dir mounted (cloud worker)."""
    if os.environ.get("ICARUS_SANDBOX", "").strip().lower() != "docker":
        return argv, job_dir
    uid = f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid") else "65534:65534"
    return (["docker", "run", "--rm", "--network", "none", "--read-only",
             "--tmpfs", "/tmp:rw,size=64m", "--cap-drop", "ALL",
             "--security-opt", "no-new-privileges:true", "--pids-limit", "128",
             "--memory", "512m", "--cpus", "1", "-u", uid,
             "-e", "HOME=/job", "-e", "LANG=C.UTF-8",
             "-v", f"{job_dir.resolve()}:/job:rw", "-w", "/job",
             os.environ.get("ICARUS_SANDBOX_IMAGE", DEFAULT_SANDBOX_IMAGE), *argv], None)


def _safe_path(job_dir: Path, rel: str) -> Path:
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"path escapes job dir: {rel}")
    full = (job_dir / p).resolve()
    if job_dir.resolve() not in full.parents and full != job_dir.resolve():
        raise ValueError(f"path escapes job dir: {rel}")
    return full


def _git_sha() -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                           text=True, timeout=10)
        if r.returncode != 0:
            return None
        return r.stdout.strip() or None
    except Exception:
        return None


def execute(job: dict, plan: dict | None, job_dir: Path) -> dict:
    record = {"plan_valid": plan is not None, "commands": [], "git_sha": None, "error": None}
    if plan is None:
        record["error"] = "no valid plan"
        return record
    allowed = job["verify_spec"].get("allowed_commands")
    try:
        for c in plan["commands"]:
            if allowed is not None and Path(c[0]).name not in allowed:
                raise PermissionError(f"vetoed disallowed command: {c[0]}")
        for f in plan["files"]:
            p = _safe_path(job_dir, f["path"])
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f["content"], encoding="utf-8")
        for argv in plan["commands"]:
            try:
                run_argv, cwd = _sandboxed(argv, job_dir)
                r = subprocess.run(run_argv, cwd=cwd, capture_output=True, text=True,
                                   timeout=CMD_TIMEOUT,
                                   env=_child_env(job_dir) if cwd is not None else None)
                record["commands"].append({"argv": argv, "exit_code": r.returncode,
                                           "stdout": r.stdout[-4000:], "stderr": r.stderr[-4000:]})
            except subprocess.TimeoutExpired:
                record["commands"].append({"argv": argv, "exit_code": -9,
                                           "stdout": "", "stderr": "timeout"})
                break
            except FileNotFoundError:
                record["commands"].append({"argv": argv, "exit_code": 127,
                                           "stdout": "", "stderr": "not found"})
                break
            if record["commands"][-1]["exit_code"] != 0:
                break
    except (ValueError, PermissionError) as e:
        record["error"] = str(e)
    record["git_sha"] = _git_sha()
    return record


def run_once(root: str | Path, reasoner, runner_id: str, lease_seconds: int = 600) -> dict:
    root = Path(root)
    ledger = Ledger(root)
    try:
        job = ledger.claim(runner_id, lease_seconds)
        if job is None:
            return {"status": "idle"}
        job_dir = root / "jobs" / job["id"] / f"attempt-{job['attempts'] + 1}"
        job_dir.mkdir(parents=True, exist_ok=True)
        try:
            plan = reasoner.plan(job["task"])
            plan_error = None
        except ReasonerError as e:
            plan, plan_error = None, str(e)
        record = execute(job, plan, job_dir)
        if plan_error:
            record["error"] = plan_error
        receipt = verify(job_dir, job["verify_spec"], record, task_id=job["id"])
        (job_dir / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        status = ledger.settle(job["id"], runner_id, receipt)
        return {"status": status, "job": job["id"], "receipt": receipt}
    finally:
        ledger.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Icarus single-cycle runner")
    ap.add_argument("--root", required=True)
    ap.add_argument("--runner-id", required=True)
    ap.add_argument("--lease-seconds", type=int, default=600)
    a = ap.parse_args(argv)
    try:
        reasoner = OpenAICompatReasoner()
    except ReasonerError as e:
        print(json.dumps({"status": "BLOCKED", "evidence": str(e)}))
        return 2
    out = run_once(a.root, reasoner, a.runner_id, a.lease_seconds)
    print(json.dumps(out))
    return 0 if out["status"] in ("idle", "done", "queued") else 1


if __name__ == "__main__":
    sys.exit(main())
