#!/usr/bin/env python3
"""Unattended CLI task runner: Discover -> Validate -> Claim -> Execute -> Verify -> Complete.

Runs as a plain process (no chat model involved): `task_runner.py --once` scans task_queue/, `--poll N` loops.
Persists one state file per task (state/<task_id>.json, atomic write + fsync) with owner/claim, attempt count,
start/end timestamps, exit status, log path, output hashes and source SHA, so an interruption or restart loses
nothing and can never be mistaken for completion.

Fail-closed ingress: a packet that is not valid JSON, fails the v3 schema, lacks authority_scope, is outside
ingress_policy.json, violates command scope / negative constraints, or contains a secret is REJECTED before claim
with a structured, hash-chained rejection receipt. Input is never repaired or inferred.
COMPLETE is reachable only through completion_gate.verify_completion(); a failed gate leaves BLOCKED/FAILED.
Attempt cap: 3 per task (persisted, so a crash counts); no re-run of a FAILED/BLOCKED packet unless its bytes change.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import socket
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("ICARUS_REPO_ROOT") or HERE)
MAX_ATTEMPTS = 3
LEASE_SECONDS = 330  # 300 s stage cap plus margin
TERMINAL = {"COMPLETE", "REJECTED", "FAILED", "BLOCKED"}
ALLOWED = {
    "DISCOVERED": {"VALIDATED", "REJECTED"},
    "VALIDATED": {"CLAIMED", "BLOCKED"},
    "CLAIMED": {"EXECUTING", "INTERRUPTED"},
    "EXECUTING": {"VERIFYING", "INTERRUPTED", "FAILED", "BLOCKED"},
    "INTERRUPTED": {"CLAIMED", "BLOCKED"},
    "VERIFYING": {"COMPLETE", "BLOCKED", "FAILED"},
}


def _load(name: str, fname: str):
    spec = importlib.util.spec_from_file_location(name, HERE / fname)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pid_alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


class Runner:
    def __init__(self, repo: Path | None = None):
        self.repo = Path(repo or REPO)
        self.h = _load("harness_runner_v3", "harness-runner-v3.py")
        self.h.REPO = self.repo
        self.gate = _load("completion_gate", "completion_gate.py")
        self.queue = self.repo / "task_queue"
        self.state_dir = self.repo / "state"
        self.processed = self.repo / "processed"
        self.me = f"task_runner@{socket.gethostname()}:{os.getpid()}"
        for d in (self.queue, self.state_dir, self.state_dir / "logs", self.processed):
            d.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------- state ---
    def _sp(self, tid):
        return self.state_dir / f"{tid}.json"

    def load_state(self, tid):
        p = self._sp(tid)
        return json.loads(p.read_text("utf-8")) if p.exists() else None

    def save_state(self, st: dict):
        p = self._sp(st["task_id"])
        tmp = p.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(st, indent=2, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, p)

    def transition(self, st: dict, new: str, note: str = "", **fields):
        old = st["state"]
        if new not in ALLOWED.get(old, set()):
            raise RuntimeError(f"illegal transition {old} -> {new}")
        if new == "COMPLETE" and not fields.get("_gate_ok"):
            raise RuntimeError("COMPLETE requires a passing independent completion gate")
        fields.pop("_gate_ok", None)
        st.update(fields)
        st["state"] = new
        st.setdefault("history", []).append({"ts": utcnow(), "from": old, "to": new, "note": note})
        if new in TERMINAL:
            st["ended_at"] = utcnow()
        self.save_state(st)

    # ------------------------------------------------------------ ingress ---
    def policy(self):
        try:
            return json.loads((self.repo / "ingress_policy.json").read_text("utf-8"))
        except (OSError, ValueError):
            return None

    def ingress(self, raw: bytes):
        """Return (packet|None, errors). Any doubt rejects."""
        pol = self.policy()
        if not pol:
            return None, ["ingress_policy.json missing or unreadable (fail closed)"]
        if len(raw) > int(pol.get("max_packet_bytes", 200000)):
            return None, ["packet exceeds max_packet_bytes"]
        try:
            packet = json.loads(raw)
        except ValueError:
            return None, ["packet is not valid JSON"]
        schema = json.loads((self.repo / self.h.SCHEMA_REL).read_text("utf-8"))
        errs = self.h.validate(packet, schema)
        if errs:
            return None, errs[:20]
        errs = []
        if not packet.get("authority_scope"):
            errs.append("authority_scope missing (authority is never inferred)")
        elif packet["authority_scope"] not in pol.get("allowed_authority_scopes", []):
            errs.append(f"authority_scope '{packet['authority_scope']}' not authorized by ingress policy")
        if packet["assigned_executor"] not in pol.get("allowed_executors", []):
            errs.append(f"assigned_executor '{packet['assigned_executor']}' not authorized by ingress policy")
        errs += self.h.command_scope_violations(packet)
        errs += self.h.negative_constraint_violations(
            packet, {f"command {s['stage_id']}": " ".join(s["command"]) for s in packet["stages"]})
        if self.h.find_secrets(raw.decode("utf-8", "replace")):
            errs.append("secret pattern present in packet")
        return (None, errs) if errs else (packet, [])

    def _append_chained(self, body: dict):
        v = self.h.verify_ledger()
        if not v["ok"]:
            return None
        body["prev_receipt_hash"] = v["head_hash"]
        body["receipt_hash"] = self.h._hash(body)
        self.h._append_receipt(body)
        return body["receipt_hash"]

    def reject(self, path: Path, raw: bytes, errors: list, tid: str | None = None):
        sha = hashlib.sha256(raw).hexdigest()
        tid = tid or f"REJECTED-{sha[:12]}"
        st = {"task_id": tid, "packet_file": path.name, "packet_sha256": sha, "state": "DISCOVERED",
              "owner": None, "attempts": 0, "history": [], "started_at": None, "ended_at": None,
              "exit_status": None, "rejection_errors": errors}
        self.save_state(st)
        rid = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-REJ-" + sha[:8]
        rh = self._append_chained({
            "schema": "icarus/rejection.v3", "run_id": rid, "task_id": tid, "packet_file": path.name,
            "packet_sha256": sha, "status": "REJECTED", "stage": "INGRESS", "errors": errors,
            "git_sha": self.h.current_sha(), "at": utcnow()})
        self.transition(st, "REJECTED", "ingress rejected", rejection_receipt_hash=rh, run_id=rid)
        self._archive(path, "REJECTED", rid)
        return st

    def _archive(self, path: Path, status: str, run_id: str):
        if path.exists():
            dest = self.processed / f"{path.stem}__{run_id}__{status}.json"
            shutil.move(str(path), dest)
            return str(dest.relative_to(self.repo))
        return None

    # ----------------------------------------------------------- recovery ---
    def recover(self):
        out = []
        for f in sorted(self.state_dir.glob("*.json")):
            st = json.loads(f.read_text("utf-8"))
            if st["state"] in ("CLAIMED", "EXECUTING"):
                dead = not pid_alive(st.get("lease_pid")) or time.time() > st.get("lease_expires_epoch", 0)
                if dead:
                    self.transition(st, "INTERRUPTED", f"runner pid {st.get('lease_pid')} gone or lease expired; attempt {st['attempts']} counted",
                                    lease_pid=None)
                    out.append(st["task_id"])
                    if st["attempts"] >= MAX_ATTEMPTS:
                        self.transition(st, "BLOCKED", "attempt cap reached after interruption; clean-slate handoff required")
        return out

    # ------------------------------------------------------------ process ---
    def process(self, path: Path):
        raw = path.read_bytes()
        packet, errors = self.ingress(raw)
        if packet is None:
            tid = None
            try:
                j = json.loads(raw)
                if isinstance(j, dict) and isinstance(j.get("task_id"), str):
                    tid = None  # never trust an unvalidated id as a state key
            except ValueError:
                pass
            return self.reject(path, raw, errors, tid)
        tid, sha = packet["task_id"], hashlib.sha256(raw).hexdigest()
        st = self.load_state(tid)
        if st and st["state"] in TERMINAL:
            if st.get("packet_sha256") == sha:  # same bytes: no blind re-run
                self._archive(path, "DUPLICATE_" + st["state"], st.get("run_id") or "none")
                return st
            prior_attempts = st.get("attempts", 0)  # a changed packet is a new approach, but the 3-attempt cap is per task_id
            st = None
        if st and st["state"] in ("CLAIMED", "EXECUTING"):
            return st  # live owner
        if st is None:
            st = {"task_id": tid, "packet_file": path.name, "packet_path": f"task_queue/{path.name}",
                  "packet_sha256": sha, "state": "DISCOVERED", "owner": None, "attempts": locals().get("prior_attempts", 0), "history": [],
                  "started_at": None, "ended_at": None, "exit_status": None}
            self.save_state(st)
            self.transition(st, "VALIDATED", "schema, authority, scope, constraints, secrets passed")
        elif st["state"] == "INTERRUPTED" and st.get("packet_sha256") != sha:
            self.transition(st, "BLOCKED", "packet changed while interrupted; resubmit as new task")
            return st
        if st["attempts"] >= MAX_ATTEMPTS:
            if st["state"] != "BLOCKED":
                self.transition(st, "BLOCKED", "attempt cap reached")
            return st
        claim = self.state_dir / f"{tid}.claim"
        try:
            fd = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, self.me.encode())
            os.close(fd)
        except FileExistsError:
            if st["state"] == "INTERRUPTED":
                claim.unlink(missing_ok=True)
                fd = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, self.me.encode())
                os.close(fd)
            else:
                return st
        self.transition(st, "CLAIMED", f"claimed by {self.me}", owner=self.me, claim_id=hashlib.sha256((tid + utcnow() + self.me).encode()).hexdigest()[:16])
        return self.execute(st, path, raw)

    def execute(self, st: dict, path: Path, raw: bytes):
        st["attempts"] += 1  # persisted before running: a crash still counts
        if st["started_at"] is None:
            st["started_at"] = utcnow()
        self.transition(st, "EXECUTING", f"attempt {st['attempts']}/{MAX_ATTEMPTS}",
                        lease_pid=os.getpid(), lease_expires_epoch=time.time() + LEASE_SECONDS, attempt_started_at=utcnow())
        result = self.h.execute_packet(path)
        r = result["receipt"]
        stages = r.get("stages") or []
        last_codes = [s["attempts"][-1]["exit_code"] for s in stages if s.get("attempts")]
        exit_status = 0 if last_codes and all(c == 0 for c in last_codes) and r["status"] == "PASS" else (
            next((c for c in last_codes if c not in (0, None)), 1))
        log_rel = f"state/logs/{st['task_id']}.attempt{st['attempts']}.log"
        (self.repo / log_rel).write_text(self.h.redact(json.dumps(
            {"receipt": r, "readback": result["readback"]}, indent=2)), "utf-8")
        st.update(run_id=r["run_id"], receipt_hash=r["receipt_hash"], source_sha=r["git_sha"],
                  exit_status=exit_status, log_path=log_rel,
                  outputs=[{"path": a["path"], "sha256": a["sha256"]} for a in r["artifacts"]],
                  receipt_status=r["status"], lease_pid=None)
        if r["status"] == "BLOCKED":
            self.transition(st, "BLOCKED", "execution vetoed by harness policy gate")
        elif r["status"] == "FAIL":
            self.transition(st, "FAILED", "execution failed Gate 1; no blind retry")
        else:
            self.transition(st, "VERIFYING", "independent completion gate")
            verdict = self.gate.verify_completion(self.repo, st, self.h)
            st["gate_verdict"] = {"ok": verdict["ok"], "checks": verdict["checks"], "errors": verdict["errors"]}
            if verdict["ok"]:
                th = self._append_chained({
                    "schema": "icarus/terminal.v3", "run_id": r["run_id"] + "-TERMINAL", "task_id": st["task_id"],
                    "status": "COMPLETE", "execution_receipt_hash": r["receipt_hash"], "attempts": st["attempts"],
                    "exit_status": 0, "git_sha": r["git_sha"], "gate_checks": verdict["checks"],
                    "verifier_tier": "TIER_1_MACHINE", "at": utcnow()})
                if th is None:
                    self.transition(st, "BLOCKED", "ledger invalid at terminal append")
                else:
                    self.transition(st, "COMPLETE", "all gate checks passed", terminal_receipt_hash=th, _gate_ok=True)
            else:
                self.transition(st, "BLOCKED", "completion gate failed: " + "; ".join(verdict["errors"][:3]))
        (self.state_dir / f"{st['task_id']}.claim").unlink(missing_ok=True)
        dest = self._archive(path, st["state"], r["run_id"])
        if dest:
            st["packet_path"] = dest  # audit re-reads the archived bytes
            self.save_state(st)
        return st

    def once(self):
        recovered = self.recover()
        done = [self.process(p) for p in sorted(self.queue.glob("*.json")) if p.is_file()]
        return {"recovered": recovered, "processed": [{"task_id": s["task_id"], "state": s["state"]} for s in done]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--poll", type=int, default=0, help="seconds between scans (loop)")
    ap.add_argument("--max-cycles", type=int, default=0)
    a = ap.parse_args(argv)
    r = Runner()
    if a.once or not a.poll:
        out = r.once()
        print(json.dumps(out, indent=2))
        return 0 if all(p["state"] == "COMPLETE" for p in out["processed"]) else 1
    n = 0
    while True:
        out = r.once()
        if out["processed"] or out["recovered"]:
            print(json.dumps(out), flush=True)
        n += 1
        if a.max_cycles and n >= a.max_cycles:
            return 0
        time.sleep(a.poll)


if __name__ == "__main__":
    sys.exit(main())
