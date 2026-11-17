"""Primitive 4 - Deterministic Verification Referee.

Independent of the reasoner and the executor: it only reads the job
directory and the execution record, applies the verify_spec that the task
author fixed at enqueue time, and returns a receipt. It never edits outputs.

Gate 1 (technical): every command exited 0, every expected file exists,
                    optional sha256 matches, optional git SHA logged.
Gate 2 (policy):    plan schema valid, zero secrets in outputs,
                    negative constraints met (only allowed commands ran,
                    no forbidden patterns in outputs).
Passing Gate 1 while failing Gate 2 is FAIL (template rule 2).

verify_spec shape:
    {"expected_files": ["out.txt", ...],
     "sha256": {"out.txt": "<hex>"},               # optional
     "require_git_sha": false,                      # optional
     "allowed_commands": ["python3", "echo"],       # optional allowlist
     "forbidden_patterns": ["DROP TABLE"]}          # optional
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

VERIFIER_ID = "icarus.primitives.verify/v1"

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
]


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _scan_secrets(text: str) -> bool:
    return any(p.search(text) for p in SECRET_PATTERNS)


def verify(job_dir: str | Path, spec: dict, execution: dict) -> dict:
    """execution = {"plan_valid": bool, "commands": [{"argv": [...], "exit_code": int,
    "stdout": str, "stderr": str}], "git_sha": str|None, "error": str|None}"""
    job_dir = Path(job_dir)
    g1: list[str] = []
    g2: list[str] = []

    # ---- Gate 1: technical
    if execution.get("error"):
        g1.append(f"execution error: {execution['error']}")
    for c in execution.get("commands", []):
        if c.get("exit_code") != 0:
            g1.append(f"exit {c.get('exit_code')}: {' '.join(c.get('argv', []))}")
    for rel in spec.get("expected_files", []):
        p = (job_dir / rel)
        if not p.is_file():
            g1.append(f"missing file: {rel}")
            continue
        want = spec.get("sha256", {}).get(rel)
        if want and _sha256(p) != want:
            g1.append(f"sha256 mismatch: {rel}")
    if spec.get("require_git_sha") and not execution.get("git_sha"):
        g1.append("git SHA not logged")

    # ---- Gate 2: policy
    if not execution.get("plan_valid"):
        g2.append("plan schema invalid")
    allowed = spec.get("allowed_commands")
    if allowed is not None:
        for c in execution.get("commands", []):
            argv0 = (c.get("argv") or [""])[0]
            if Path(argv0).name not in allowed:
                g2.append(f"disallowed command ran: {argv0}")
    texts = []
    for p in sorted(job_dir.rglob("*")) if job_dir.exists() else []:
        if p.is_file():
            try:
                texts.append(p.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                pass
    for c in execution.get("commands", []):
        texts.append(c.get("stdout", ""))
        texts.append(c.get("stderr", ""))
    blob = "\n".join(texts)
    if _scan_secrets(blob):
        g2.append("secret detected in outputs")
    for pat in spec.get("forbidden_patterns", []):
        if pat in blob:
            g2.append(f"forbidden pattern present: {pat}")

    files = {}
    for rel in spec.get("expected_files", []):
        p = job_dir / rel
        if p.is_file():
            files[rel] = _sha256(p)

    return {
        "verifier": VERIFIER_ID,
        "verdict": "PASS" if not g1 and not g2 else "FAIL",
        "gate_1_technical": {"pass": not g1, "reasons": g1},
        "gate_2_policy": {"pass": not g2, "reasons": g2},
        "files_sha256": files,
        "git_sha": execution.get("git_sha"),
    }
