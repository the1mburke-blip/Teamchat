"""Primitive 1 (distributed) - ledger that lives in the git repo.

Both runtimes can reach it: the Apps Script pulse (GitHub contents API) and
the Docker daemon (git). Git is the open format; GitHub is only the host.

Layout under <clone>/icarus/ledger/:
    queue/<job_id>.json   immutable job: task + verify_spec + author (written at enqueue)
    state/<job_id>.json   {status, attempts, max_attempts, claimed_by, lease_expires}
    run_log.jsonl         append-only, hash-chained events and receipts

Locking: a claim is a commit that rewrites state/<job_id>.json, then a push.
If the push is rejected (someone else moved the branch), the claim is lost:
re-sync from the remote and re-read; never assume the claim stuck.

The clone passed in MUST be dedicated to the daemon: sync() hard-resets it to
the remote branch. Never point it at a working copy with local edits.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

LEDGER_DIR = "icarus/ledger"
QUEUED, CLAIMED, DONE, BLOCKED = "queued", "claimed", "done", "BLOCKER_DISCOVERED"
FINAL = {DONE, BLOCKED}
GENESIS = "0" * 64


class GitLedgerError(Exception):
    pass


class ClaimLost(GitLedgerError):
    pass


def chain_append(log_path: Path, event: dict) -> dict:
    prev = GENESIS
    if log_path.exists():
        lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            prev = json.loads(lines[-1])["hash"]
    body = {"ts": time.time(), "prev": prev, **event}
    body["hash"] = hashlib.sha256((prev + json.dumps(body, sort_keys=True)).encode()).hexdigest()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(body, sort_keys=True) + "\n")
    return body


def chain_ok(log_path: Path) -> bool:
    prev = GENESIS
    if not log_path.exists():
        return True
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        h = rec.pop("hash")
        if rec.get("prev") != prev:
            return False
        if hashlib.sha256((prev + json.dumps(rec, sort_keys=True)).encode()).hexdigest() != h:
            return False
        prev = h
    return True


class GitLedger:
    def __init__(self, clone: str | Path, branch: str, remote: str = "origin"):
        self.clone = Path(clone)
        self.branch = branch
        self.remote = remote
        self.base = self.clone / LEDGER_DIR
        self.log_path = self.base / "run_log.jsonl"

    # ---- git plumbing ----------------------------------------------------
    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        r = subprocess.run(["git", *args], cwd=self.clone, capture_output=True, text=True,
                           timeout=120)
        if check and r.returncode != 0:
            raise GitLedgerError(f"git {' '.join(args)}: {r.stderr.strip()[:500]}")
        return r

    def sync(self) -> None:
        self._git("fetch", "--quiet", self.remote, self.branch)
        self._git("reset", "--quiet", "--hard", f"{self.remote}/{self.branch}")

    def _commit_push(self, paths: list[Path], message: str) -> bool:
        """Commit paths and push. Returns False if the push was rejected."""
        self._git("add", "--", *[str(p.relative_to(self.clone)) for p in paths])
        self._git("-c", "user.name=icarus-daemon", "-c", "user.email=icarus-daemon@localhost",
                  "commit", "--quiet", "-m", message)
        r = self._git("push", "--quiet", self.remote, f"HEAD:{self.branch}", check=False)
        return r.returncode == 0

    def head(self) -> str:
        return self._git("rev-parse", "HEAD").stdout.strip()

    def record_tool_call(self, job_id: str, runner_id: str, event: dict, tries: int = 3) -> None:
        """Persist each sanitized external-tool event in the hash-chained ledger."""
        if not isinstance(event, dict) or not event.get("tool_slug") or not event.get("status"):
            raise GitLedgerError("tool event requires tool_slug and status")
        for _ in range(tries):
            self.sync()
            chain_append(self.log_path, {"type": "tool_call", "job": job_id,
                                         "runner": runner_id, "event": event})
            if self._commit_push([self.log_path], "ledger: record external tool call"):
                return
        raise GitLedgerError(f"tool event for {job_id} not pushed after {tries} fresh re-syncs")

    # ---- reads -------------------------------------------------------------
    def _read(self, kind: str, job_id: str) -> dict | None:
        p = self.base / kind / f"{job_id}.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def job(self, job_id: str) -> dict:
        q = self._read("queue", job_id)
        if q is None:
            raise GitLedgerError(f"no job {job_id}")
        s = self._read("state", job_id) or {"status": QUEUED, "attempts": 0,
                                             "max_attempts": q.get("max_attempts", 3)}
        return {**q, "id": job_id, "state": s}

    def job_ids(self) -> list[str]:
        d = self.base / "queue"
        if not d.exists():
            return []
        return sorted(p.stem for p in d.glob("*.json"))

    # ---- writes ------------------------------------------------------------
    def enqueue(self, job_id: str, task: dict, verify_spec: dict, author: str,
                max_attempts: int = 3) -> None:
        if not verify_spec or not isinstance(verify_spec, dict):
            raise GitLedgerError("verify_spec must be set at enqueue time")
        if not author:
            raise GitLedgerError("author required")
        self.sync()
        q = self.base / "queue" / f"{job_id}.json"
        if q.exists():
            raise GitLedgerError(f"job {job_id} already exists")
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_text(json.dumps({"task": task, "verify_spec": verify_spec, "author": author,
                                 "max_attempts": max_attempts}, indent=2, sort_keys=True),
                     encoding="utf-8")
        chain_append(self.log_path, {"type": "enqueued", "job": job_id, "author": author})
        if not self._commit_push([q, self.log_path], f"ledger: enqueue {job_id}"):
            self.sync()
            raise GitLedgerError("enqueue push rejected; re-synced, nothing queued")

    def claim(self, runner_id: str, lease_seconds: int = 900, host: str = "any") -> dict | None:
        """Claim one claimable job. Returns None when idle; raises ClaimLost on a race.
        host="cloud" skips jobs whose queue file sets "execution_target": "laptop-only"."""
        self.sync()
        now = time.time()
        for job_id in self.job_ids():
            j = self.job(job_id)
            s = j["state"]
            if s["status"] in FINAL:
                continue
            if host == "cloud" and j.get("execution_target") == "laptop-only":
                continue
            if s["status"] == CLAIMED and s.get("lease_expires", 0) > now:
                continue
            s.update({"status": CLAIMED, "claimed_by": runner_id,
                      "lease_expires": now + lease_seconds})
            sp = self.base / "state" / f"{job_id}.json"
            sp.parent.mkdir(parents=True, exist_ok=True)
            sp.write_text(json.dumps(s, indent=2, sort_keys=True), encoding="utf-8")
            chain_append(self.log_path, {"type": "claimed", "job": job_id, "runner": runner_id})
            if not self._commit_push([sp, self.log_path], f"ledger: {runner_id} claims {job_id}"):
                self.sync()
                raise ClaimLost(job_id)
            return self.job(job_id)
        return None

    def settle(self, job_id: str, runner_id: str, receipt: dict, tries: int = 3) -> str:
        if receipt.get("verifier") is None or receipt.get("verdict") not in ("PASS", "FAIL"):
            raise GitLedgerError("settle requires a verifier receipt")
        for _ in range(tries):
            self.sync()
            s = self.job(job_id)["state"]
            if s["status"] != CLAIMED or s.get("claimed_by") != runner_id:
                raise ClaimLost(job_id)
            attempts = s.get("attempts", 0) + 1
            if receipt["verdict"] == "PASS":
                status = DONE
            elif attempts >= s.get("max_attempts", 3):
                status = BLOCKED
            else:
                status = QUEUED
            s.update({"status": status, "attempts": attempts, "claimed_by": None,
                      "lease_expires": None})
            sp = self.base / "state" / f"{job_id}.json"
            sp.write_text(json.dumps(s, indent=2, sort_keys=True), encoding="utf-8")
            chain_append(self.log_path, {"type": "receipt", "job": job_id, "runner": runner_id,
                                         "attempt": attempts, "status": status,
                                         "receipt": receipt})
            if self._commit_push([sp, self.log_path], f"ledger: {job_id} -> {status}"):
                return status
            # remote moved (another job's claim); re-sync and recompute from fresh state
        raise GitLedgerError(f"settle of {job_id} not pushed after {tries} fresh re-syncs")
