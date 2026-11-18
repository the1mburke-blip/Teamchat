#!/usr/bin/env python3
"""Unattended task runner: Discover -> Validate -> Claim -> Execute -> (hand off to) Verify.

The runner can never mark a task COMPLETE. After execution it sets PENDING_VERIFICATION and
spawns the independent verifier as a separate process; only the verifier's verdict, checked by
Store.complete(), can reach COMPLETE.

Usage:
  python3 -m execboundary.runner --root STATE_DIR --repo GIT_WORKTREE [--once | --loop --interval N]
Exit codes (--once): 0 = cycle ran; 3 = execution capability absent (git missing / repo not a git worktree).
"""
import argparse
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from execboundary import schema
from execboundary.store import LedgerError, Store, now, safe_id, sha256_file

ATTEMPT_TIMEOUT = schema.MAX_TIMEOUT
MAX_ATTEMPTS = schema.MAX_ATTEMPTS


def git_head(repo):
    r = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("git rev-parse failed: " + r.stderr.strip())
    return r.stdout.strip()


def tree_fingerprint(repo, paths):
    """sha256 over (relpath, file sha256) for every file under each path; missing paths hash as absent."""
    h = hashlib.sha256()
    repo = Path(repo)
    for p in sorted(paths):
        target = repo / p
        files = []
        if target.is_file():
            files = [target]
        elif target.is_dir():
            files = sorted(x for x in target.rglob("*") if x.is_file() and ".git" not in x.parts)
        h.update(("PATH:" + p + ("" if files else ":ABSENT") + "\n").encode())
        for f in files:
            h.update(("%s %s\n" % (f.relative_to(repo).as_posix(), sha256_file(f))).encode())
    return h.hexdigest()


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class Runner:
    def __init__(self, root, repo, owner="execboundary.runner", spawn_verifier=True):
        self.store = Store(root)
        self.repo = Path(repo).resolve()
        self.owner = owner
        self.spawn_verifier = spawn_verifier

    # ---- capability check -------------------------------------------------
    def capability(self):
        if shutil.which("git") is None:
            return "git not installed"
        try:
            git_head(self.repo)
        except RuntimeError as e:
            return str(e)
        return None

    # ---- recovery ---------------------------------------------------------
    def recover(self):
        for st in self.store.all_tasks():
            if st["status"] not in ("CLAIMED", "RUNNING"):
                continue
            claim = self.store.claim_owner(st["task_id"]) or {}
            same_host = claim.get("host") == socket.gethostname()
            if same_host and claim.get("pid") and pid_alive(claim["pid"]) and claim["pid"] != os.getpid():
                continue  # live executor elsewhere on this host; leave it alone
            self.store.release(st["task_id"])
            st.update(status="INTERRUPTED", interrupted_at=now())
            self.store.put(st)
            self.store.receipt(st["task_id"], "INTERRUPTED", {"attempt": st["attempt"], "prior_claim": claim})

    # ---- discovery + ingress -----------------------------------------------
    def discover(self):
        return sorted(p for p in (self.store.root / "inbox").iterdir() if p.is_file() and p.suffix == ".json")

    def reject(self, path, raw, code, detail, task_id="_ingress"):
        digest = hashlib.sha256(raw).hexdigest()
        dest = self.store.root / "rejected" / ("%s-%s.json" % (now().replace(":", ""), digest[:12]))
        os.replace(path, dest)
        self.store.receipt(task_id, "REJECTED", {"code": code, "detail": detail, "input_sha256": digest,
                                                 "input_file": path.name, "moved_to": dest.name})

    def ingest(self, path):
        raw = path.read_bytes()
        try:
            env, digest = schema.validate_envelope(raw)
        except schema.Rejected as e:
            self.reject(path, raw, e.code, e.detail)
            return None
        task_id = env["packet"]["task_id"]
        try:
            safe_id(task_id)
        except LedgerError as e:
            self.reject(path, raw, "CONSTRAINT_VIOLATION", str(e))
            return None
        st = self.store.get(task_id)
        if st:
            if st["status"] in ("COMPLETE", "BLOCKER_DISCOVERED"):
                self.reject(path, raw, "TASK_TERMINAL", st["status"], task_id)
                return None
            if st["status"] in ("CLAIMED", "RUNNING", "PENDING_VERIFICATION", "INTERRUPTED"):
                self.reject(path, raw, "TASK_ACTIVE", st["status"], task_id)
                return None
            if digest in st["packet_history"]:
                self.reject(path, raw, "BLIND_RETRY", "identical packet already attempted", task_id)
                return None
            if st["attempt"] >= MAX_ATTEMPTS:
                self.reject(path, raw, "ATTEMPTS_EXHAUSTED", str(st["attempt"]), task_id)
                return None
        pkt = self.store.root / "packets" / (digest + ".json")
        if not pkt.exists():
            fd = os.open(pkt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
        path.unlink()
        history = (st or {}).get("packet_history", []) + [digest]
        state = dict(st or {}, task_id=task_id, packet_sha256=digest, packet_history=history,
                     attempt=(st or {}).get("attempt", 0), validated_at=now())
        self.store.receipt(task_id, "VALIDATED", {"packet_sha256": digest, "input_file": path.name})
        return state

    # ---- claim + execute -----------------------------------------------------
    def execute(self, state):
        task_id = state["task_id"]
        owner = {"owner": self.owner, "pid": os.getpid(), "host": socket.gethostname(), "claimed_at": now()}
        if not self.store.claim(task_id, owner):
            self.store.receipt(task_id, "CLAIM_REFUSED", {"holder": self.store.claim_owner(task_id)})
            return state
        raw = (self.store.root / "packets" / (state["packet_sha256"] + ".json")).read_bytes()
        env, _ = schema.validate_envelope(raw)  # re-validate at claim: fail closed if template/authority changed
        ex = env["execution"]
        attempt = state["attempt"] + 1
        git_sha = git_head(self.repo)
        forbidden = schema.effective_forbidden(env)
        state.update(status="CLAIMED", attempt=attempt, claim=owner, git_sha=git_sha,
                     forbidden_fingerprint_before=tree_fingerprint(self.repo, forbidden))
        self.store.put(state)
        self.store.receipt(task_id, "CLAIMED", {"attempt": attempt, "owner": owner, "git_sha": git_sha,
                                                "packet_sha256": state["packet_sha256"]})
        logdir = self.store.root / "logs" / task_id / ("attempt-%d" % attempt)
        logdir.mkdir(parents=True, exist_ok=True)
        state.update(status="RUNNING", started_at=now(), log_dir=str(logdir.relative_to(self.store.root)))
        self.store.put(state)
        deadline = time.monotonic() + ATTEMPT_TIMEOUT
        results = []
        failed = None
        for i, argv in enumerate(ex["commands"]):
            remaining = deadline - time.monotonic()
            out_p, err_p = logdir / ("cmd-%d.stdout" % i), logdir / ("cmd-%d.stderr" % i)
            if remaining <= 0:
                failed = "TIMEOUT"
                results.append({"argv": argv, "exit_code": None, "error": "attempt wall clock exhausted"})
                break
            with open(out_p, "wb") as o, open(err_p, "wb") as e:
                try:
                    proc = subprocess.run(argv, cwd=self.repo, stdout=o, stderr=e, stdin=subprocess.DEVNULL,
                                          timeout=remaining, shell=False)
                    code = proc.returncode
                except subprocess.TimeoutExpired:
                    code, failed = None, "TIMEOUT"
                except OSError as exc:
                    e.write(str(exc).encode())
                    code, failed = 127, "EXEC_ERROR"
            results.append({"argv": argv, "exit_code": code, "stdout": out_p.name, "stderr": err_p.name,
                            "stdout_sha256": sha256_file(out_p), "stderr_sha256": sha256_file(err_p)})
            if code != 0:
                failed = failed or "NONZERO_EXIT"
                break
        outputs = {}
        for rel in ex["required_outputs"]:
            p = self.repo / rel
            outputs[rel] = sha256_file(p) if p.is_file() else None
        state.update(ended_at=now(), commands=results, outputs=outputs,
                     exit_code=0 if failed is None else (results[-1]["exit_code"] if results else None))
        self.store.release(task_id)
        if failed:
            terminal = attempt >= MAX_ATTEMPTS
            state.update(status="BLOCKER_DISCOVERED" if terminal else "FAILED", failure=failed)
            self.store.put(state)
            self.store.receipt(task_id, "FAILED", {"attempt": attempt, "failure": failed, "commands": results})
            if terminal:
                self.dossier(state)
            return state
        state.update(status="PENDING_VERIFICATION")
        self.store.put(state)
        self.store.receipt(task_id, "EXECUTED", {"attempt": attempt, "commands": results, "outputs": outputs,
                                                 "git_sha": git_sha})
        if self.spawn_verifier:
            self.verify(task_id)
        return self.store.get(task_id)

    def verify(self, task_id):
        """Independent verification in a separate interpreter (-I: isolated, ignores env/user site)."""
        pkg_parent = str(Path(__file__).resolve().parent.parent)
        cmd = [sys.executable, "-I", "-c",
               "import sys; sys.path.insert(0, %r); from execboundary.verifier import main; sys.exit(main())" % pkg_parent,
               "--root", str(self.store.root), "--repo", str(self.repo), task_id]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=ATTEMPT_TIMEOUT + 60)

    def dossier(self, state):
        body = {"status": "BLOCKER_DISCOVERED", "task_id": state["task_id"], "attempts": state["attempt"],
                "packet_history": state["packet_history"], "last_failure": state.get("failure"),
                "last_commands": state.get("commands"), "log_dir": state.get("log_dir"),
                "git_sha": state.get("git_sha"),
                "handoff": "Open a clean-slate issue for the next peer agent with this dossier; no transcript inheritance."}
        self.store.receipt(state["task_id"], "BLOCKER_DISCOVERED", body)

    # ---- one cycle ------------------------------------------------------------
    def cycle(self):
        self.recover()
        for st in self.store.all_tasks():  # re-run interrupted attempts (recovery, not a blind retry)
            if st["status"] == "INTERRUPTED":
                if st["attempt"] >= MAX_ATTEMPTS:
                    st.update(status="BLOCKER_DISCOVERED", failure="INTERRUPTED_AT_LIMIT")
                    self.store.put(st)
                    self.dossier(st)
                else:
                    self.execute(st)
            elif st["status"] == "PENDING_VERIFICATION" and self.spawn_verifier:
                self.verify(st["task_id"])
        for path in self.discover():
            state = self.ingest(path)
            if state is not None:
                self.execute(state)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--repo", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--once", action="store_true")
    g.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=float, default=30.0)
    a = ap.parse_args(argv)
    r = Runner(a.root, a.repo)
    missing = r.capability()
    if missing:
        sys.stderr.write("BLOCKED: execution capability absent\nEvidence: %s\n" % missing)
        return 3
    if a.once:
        r.cycle()
        return 0
    stop = {"flag": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.update(flag=True))
    while not stop["flag"]:
        r.cycle()
        time.sleep(a.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
