"""Primitive 1 - Canonical State & Evidence Ledger.

Open formats only: SQLite for the task queue (atomic claims), JSONL for the
append-only, hash-chained run log. No vendor API.

Rules enforced here:
- pass criteria (verify_spec) are fixed at enqueue time by the task author,
  before any executor sees the job (template rule 1 + rule 3);
- claims are atomic with an expiring lease, so two runners never take the
  same job (closes the locking gap);
- attempts are capped; the job goes BLOCKER_DISCOVERED after max_attempts
  (template rule 4);
- the run log is append-only and hash-chained, so edits are detectable
  (template rule 7).
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path

QUEUED = "queued"
CLAIMED = "claimed"
DONE = "done"
BLOCKED = "BLOCKER_DISCOVERED"
GENESIS = "0" * 64


class LedgerError(Exception):
    pass


def _now() -> float:
    return time.time()


class Ledger:
    def __init__(self, root: str | os.PathLike):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "ledger.db"
        self.log_path = self.root / "run_log.jsonl"
        self._db = sqlite3.connect(self.db_path, isolation_level=None, timeout=30)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                task TEXT NOT NULL,
                verify_spec TEXT NOT NULL,
                author TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                claimed_by TEXT,
                lease_expires REAL,
                created REAL NOT NULL,
                updated REAL NOT NULL
            )"""
        )

    def close(self) -> None:
        self._db.close()

    # ---- queue -----------------------------------------------------------
    def enqueue(self, job_id: str, task: dict, verify_spec: dict, author: str,
                max_attempts: int = 3) -> None:
        if not verify_spec or not isinstance(verify_spec, dict):
            raise LedgerError("verify_spec must be set at enqueue time")
        if not author:
            raise LedgerError("author required")
        t = _now()
        try:
            self._db.execute(
                "INSERT INTO jobs (id, task, verify_spec, author, status, max_attempts,"
                " created, updated) VALUES (?,?,?,?,?,?,?,?)",
                (job_id, json.dumps(task), json.dumps(verify_spec), author, QUEUED,
                 max_attempts, t, t),
            )
        except sqlite3.IntegrityError as e:
            raise LedgerError(f"job {job_id} already exists") from e
        self.append({"type": "enqueued", "job": job_id, "author": author})

    def claim(self, runner_id: str, lease_seconds: int = 600) -> dict | None:
        """Atomically claim one queued job (or one whose lease expired)."""
        t = _now()
        self._db.execute("BEGIN IMMEDIATE")
        try:
            row = self._db.execute(
                "SELECT id FROM jobs WHERE status=? OR (status=? AND lease_expires<?)"
                " ORDER BY created LIMIT 1",
                (QUEUED, CLAIMED, t),
            ).fetchone()
            if row is None:
                self._db.execute("COMMIT")
                return None
            self._db.execute(
                "UPDATE jobs SET status=?, claimed_by=?, lease_expires=?, updated=?"
                " WHERE id=?",
                (CLAIMED, runner_id, t + lease_seconds, t, row[0]),
            )
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise
        self.append({"type": "claimed", "job": row[0], "runner": runner_id})
        return self.get(row[0])

    def get(self, job_id: str) -> dict:
        r = self._db.execute(
            "SELECT id, task, verify_spec, author, status, attempts, max_attempts,"
            " claimed_by, lease_expires FROM jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        if r is None:
            raise LedgerError(f"no job {job_id}")
        return {
            "id": r[0], "task": json.loads(r[1]), "verify_spec": json.loads(r[2]),
            "author": r[3], "status": r[4], "attempts": r[5], "max_attempts": r[6],
            "claimed_by": r[7], "lease_expires": r[8],
        }

    def settle(self, job_id: str, runner_id: str, receipt: dict) -> str:
        """Apply a verifier receipt. Only the claiming runner may settle."""
        job = self.get(job_id)
        if job["status"] != CLAIMED or job["claimed_by"] != runner_id:
            raise LedgerError(f"{runner_id} does not hold {job_id}")
        if receipt.get("verifier") is None or receipt.get("verdict") not in ("PASS", "FAIL"):
            raise LedgerError("settle requires a verifier receipt")
        attempts = job["attempts"] + 1
        if receipt["verdict"] == "PASS":
            status = DONE
        elif attempts >= job["max_attempts"]:
            status = BLOCKED
        else:
            status = QUEUED
        self._db.execute(
            "UPDATE jobs SET status=?, attempts=?, claimed_by=NULL, lease_expires=NULL,"
            " updated=? WHERE id=?",
            (status, attempts, _now(), job_id),
        )
        self.append({"type": "receipt", "job": job_id, "runner": runner_id,
                     "attempt": attempts, "status": status, "receipt": receipt})
        return status

    # ---- append-only run log ----------------------------------------------
    def _last_hash(self) -> str:
        if not self.log_path.exists():
            return GENESIS
        last = None
        with self.log_path.open("rb") as f:
            for line in f:
                if line.strip():
                    last = line
        return json.loads(last)["hash"] if last else GENESIS

    def append(self, event: dict) -> dict:
        prev = self._last_hash()
        body = {"ts": _now(), "prev": prev, **event}
        digest = hashlib.sha256(
            (prev + json.dumps(body, sort_keys=True)).encode()
        ).hexdigest()
        body["hash"] = digest
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(body, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return body

    def verify_chain(self) -> bool:
        prev = GENESIS
        if not self.log_path.exists():
            return True
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            h = rec.pop("hash")
            if rec.get("prev") != prev:
                return False
            calc = hashlib.sha256((prev + json.dumps(rec, sort_keys=True)).encode()).hexdigest()
            if calc != h:
                return False
            prev = h
        return True
