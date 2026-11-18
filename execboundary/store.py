"""Persistent task state, write-once receipts and a hash-chained append-only ledger.

Layout under ROOT:
  inbox/                 packets awaiting discovery (owner-controlled)
  packets/<sha>.json     raw accepted packet bytes (write-once)
  rejected/<ts>-<sha>.json  rejected inputs, moved out of the inbox
  tasks/<task_id>.json   current task state (atomic replace)
  claims/<task_id>.lock  single-executor claim (O_EXCL)
  receipts/<task_id>/<n>-<event>.json  write-once receipts
  logs/<task_id>/attempt-<n>/...       captured stdout/stderr
  ledger.jsonl           append-only, each row chains the previous row's sha256
"""
import datetime
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path

STATES = ("CLAIMED", "RUNNING", "INTERRUPTED", "FAILED", "PENDING_VERIFICATION",
          "VERIFICATION_FAILED", "BLOCKER_DISCOVERED", "COMPLETE")
TERMINAL = ("COMPLETE", "BLOCKER_DISCOVERED")
GENESIS = "0" * 64
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
COMPLETE_GATES = ("exit_code_zero", "outputs_exist", "git_sha_logged",
                  "schema_valid", "zero_secrets", "negative_constraints_met", "tests_passed")


class LedgerError(RuntimeError):
    pass


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_id(task_id):
    if not SAFE_ID.match(task_id):
        raise LedgerError("unsafe task_id: %r" % task_id)
    return task_id


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        for d in ("inbox", "packets", "rejected", "tasks", "claims", "receipts", "logs"):
            (self.root / d).mkdir(parents=True, exist_ok=True)
        self.ledger = self.root / "ledger.jsonl"
        self.ledger.touch(exist_ok=True)

    # ---- ledger ---------------------------------------------------------
    def _last_hash(self, f):
        f.seek(0)
        last = GENESIS
        for line in f:
            if line.strip():
                last = json.loads(line)["row_sha256"]
        return last

    def append(self, event, task_id, data):
        with open(self.ledger, "a+", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            prev = self._last_hash(f)
            row = {"ts": now(), "event": event, "task_id": task_id, "data": data, "prev_sha256": prev}
            row["row_sha256"] = hashlib.sha256(canon(row).encode()).hexdigest()
            f.seek(0, os.SEEK_END)
            f.write(canon(row) + "\n")
            f.flush()
            os.fsync(f.fileno())
            fcntl.flock(f, fcntl.LOCK_UN)
        return row

    def verify_chain(self):
        prev = GENESIS
        n = 0
        with open(self.ledger, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                claimed = row.pop("row_sha256")
                if row["prev_sha256"] != prev:
                    raise LedgerError("chain broken at line %d" % i)
                if hashlib.sha256(canon(row).encode()).hexdigest() != claimed:
                    raise LedgerError("row hash mismatch at line %d" % i)
                prev = claimed
                n += 1
        return n, prev

    # ---- receipts (write-once) -----------------------------------------
    def receipt(self, task_id, event, data):
        d = self.root / "receipts" / safe_id(task_id)
        d.mkdir(parents=True, exist_ok=True)
        n = len(list(d.iterdir())) + 1
        path = d / ("%03d-%s.json" % (n, event))
        body = {"ts": now(), "event": event, "task_id": task_id, "data": data}
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(body, indent=2, sort_keys=True))
            f.flush()
            os.fsync(f.fileno())
        row = self.append(event, task_id, dict(data, receipt=str(path.relative_to(self.root)),
                                                receipt_sha256=sha256_file(path)))
        return path, row

    # ---- task state -----------------------------------------------------
    def task_path(self, task_id):
        return self.root / "tasks" / (safe_id(task_id) + ".json")

    def get(self, task_id):
        p = self.task_path(task_id)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def put(self, state):
        if state["status"] not in STATES:
            raise LedgerError("unknown status " + state["status"])
        if state["status"] == "COMPLETE":
            raise LedgerError("COMPLETE may only be written by Store.complete()")
        self._write(state)

    def _write(self, state):
        p = self.task_path(state["task_id"])
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, p)

    def all_tasks(self):
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((self.root / "tasks").glob("*.json"))]

    # ---- claims ---------------------------------------------------------
    def claim(self, task_id, owner):
        p = self.root / "claims" / (safe_id(task_id) + ".lock")
        try:
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            return False
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(owner))
        return True

    def claim_owner(self, task_id):
        p = self.root / "claims" / (safe_id(task_id) + ".lock")
        return json.loads(p.read_text()) if p.exists() else None

    def release(self, task_id):
        p = self.root / "claims" / (safe_id(task_id) + ".lock")
        if p.exists():
            p.unlink()

    # ---- the only path to COMPLETE ---------------------------------------
    def complete(self, task_id, verdict):
        st = self.get(task_id)
        if st is None or st["status"] != "PENDING_VERIFICATION":
            raise LedgerError("COMPLETE requires PENDING_VERIFICATION, got %r" % (st and st["status"]))
        if verdict.get("verifier") != "execboundary.verifier":
            raise LedgerError("verdict not produced by the independent verifier")
        gates = verdict.get("gates", {})
        missing = [g for g in COMPLETE_GATES if gates.get(g) is not True]
        if missing or verdict.get("result") != "PASS":
            raise LedgerError("gates not all true: " + ",".join(missing))
        if verdict.get("packet_sha256") != st["packet_sha256"] or verdict.get("attempt") != st["attempt"]:
            raise LedgerError("verdict does not match current task attempt")
        path, row = self.receipt(task_id, "COMPLETE", {"verdict": verdict, "attempt": st["attempt"],
                                                         "git_sha": st["git_sha"]})
        st.update(status="COMPLETE", completed_at=now(), terminal_receipt=str(path.relative_to(self.root)),
                  terminal_row_sha256=row["row_sha256"])
        self._write(st)
        self.release(task_id)
        return st
