"""Icarus kernel: deterministic rules enforced in code.

Part of Core, not a layer above it. The kernel never calls a model and never trusts one:
everything a reasoner or a hand says is input to be checked. PASS exists only here.
"""
from __future__ import annotations

import hashlib
import json
import os
import posixpath
import time
from dataclasses import dataclass

# Writes and deletes under these prefixes are always denied (identity, rules, kernel, policy, creds, logs).
PROTECTED_DEFAULT = (
    "icarus/memory/identity.md",
    "icarus/agent/",
    "icarus/policy/",
    "icarus/runtime/",
    ".git/",
    ".github/",
)
# Any path touching these is denied for every tool, reads included.
SECRET_MARKERS = (".env", ".pem", ".credentials", "id_rsa", ".dpapi")
WRITE_TOOLS = frozenset({"write_file", "delete_file"})
PATH_KEYS = ("path", "src", "dst")
MAX_CONSECUTIVE_DENIALS = 5


@dataclass(frozen=True)
class Grant:
    """Per-task authority. Default deny: a tool or path not listed here does not run."""

    task_id: str
    allowed_tools: frozenset
    allowed_paths: tuple = ("",)  # prefixes; "" = anywhere inside the workdir
    max_calls: int = 20
    expires_at: float = float("inf")


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class Verdict:
    verdict: str  # "PASS" or "FAIL" only
    reasons: tuple


def norm_path(p):
    """Normalise a repo-relative path, or return None if it is not safe to use."""
    if not isinstance(p, str) or not p.strip() or "\x00" in p:
        return None
    if "\\" in p or p.startswith("/") or (len(p) > 1 and p[1] == ":"):
        return None
    if any(c in p for c in "~%$"):
        return None
    n = posixpath.normpath(p)
    if n == ".." or n.startswith("../") or n == ".":
        return None
    return n


def under(n, prefix):
    prefix = prefix.rstrip("/")
    return prefix == "" or n == prefix or n.startswith(prefix + "/")


class Kernel:
    def __init__(self, log_path, workdir, protected=PROTECTED_DEFAULT, clock=time.time):
        self.log_path = log_path
        self.workdir = os.path.abspath(workdir)
        self.protected = tuple(protected)
        self.clock = clock
        self._attempts = {}
        self._denials = {}

    # ---- append-only, hash-chained decision log (written by Core, outside any worker's reach)
    def _last_hash(self):
        if not os.path.exists(self.log_path):
            return "0" * 64
        last = "0" * 64
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    last = json.loads(line)["hash"]
        return last

    def log(self, event):
        body = {"ts": self.clock(), "prev": self._last_hash(), "event": event}
        raw = json.dumps(body, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        os.makedirs(os.path.dirname(os.path.abspath(self.log_path)), exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"body": body, "hash": digest}, sort_keys=True) + "\n")

    def verify_log(self):
        prev = "0" * 64
        if not os.path.exists(self.log_path):
            return True
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                body = rec["body"]
                raw = json.dumps(body, sort_keys=True, separators=(",", ":"))
                if body["prev"] != prev or hashlib.sha256(raw.encode("utf-8")).hexdigest() != rec["hash"]:
                    return False
                prev = rec["hash"]
        return True

    # ---- authorisation
    def halted(self, task_id):
        return self._denials.get(task_id, 0) >= MAX_CONSECUTIVE_DENIALS

    def authorize(self, grant, tool, args):
        d = self._decide(grant, tool, args if isinstance(args, dict) else {})
        tid = grant.task_id
        self._attempts[tid] = self._attempts.get(tid, 0) + 1
        self._denials[tid] = 0 if d.allowed else self._denials.get(tid, 0) + 1
        self.log({"type": "authorize", "task": tid, "tool": tool, "args": args, "allowed": d.allowed, "reason": d.reason})
        return d

    def _decide(self, grant, tool, args):
        tid = grant.task_id
        if self.halted(tid):
            return Decision(False, "halted after repeated denials")
        if self.clock() > grant.expires_at:
            return Decision(False, "grant expired")
        if self._attempts.get(tid, 0) >= grant.max_calls:
            return Decision(False, "budget exhausted")
        if tool not in grant.allowed_tools:
            return Decision(False, "tool not granted")
        for key in PATH_KEYS:
            if key not in args:
                continue
            n = norm_path(args[key])
            if n is None:
                return Decision(False, "invalid path")
            if any(m in n.lower() for m in SECRET_MARKERS):
                return Decision(False, "credential path")
            if not any(under(n, p) for p in grant.allowed_paths):
                return Decision(False, "path outside grant")
            if tool in WRITE_TOOLS and any(under(n, p) for p in self.protected):
                return Decision(False, "protected path")
        return Decision(True, "granted")

    # ---- adjudication: the only place PASS is produced. Binary. The worker's own claim is ignored.
    def adjudicate(self, task_id, evidence):
        reasons = []
        if not evidence or not isinstance(evidence, list):
            reasons.append("no evidence")
        else:
            for item in evidence:
                reasons.append(self._check(item))
        failed = tuple(r for r in reasons if r != "ok")
        v = Verdict("PASS" if not failed else "FAIL", failed)
        self.log({"type": "verdict", "task": task_id, "verdict": v.verdict, "reasons": list(v.reasons)})
        return v

    def _check(self, item):
        if not isinstance(item, dict):
            return "evidence item is not an object"
        n = norm_path(item.get("path"))
        if n is None:
            return "evidence path invalid"
        full = os.path.join(self.workdir, n)
        kind = item.get("kind")
        if kind == "file_exists":
            return "ok" if os.path.isfile(full) else f"missing file {n}"
        if not os.path.isfile(full):
            return f"missing file {n}"
        with open(full, "rb") as f:
            data = f.read()
        if kind == "file_sha256":
            return "ok" if hashlib.sha256(data).hexdigest() == item.get("sha256") else f"sha256 mismatch {n}"
        if kind == "text_contains":
            text = item.get("text")
            return "ok" if isinstance(text, str) and text and text.encode("utf-8") in data else f"text not found in {n}"
        return f"unknown evidence kind {kind!r}"
