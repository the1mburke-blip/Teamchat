#!/usr/bin/env python3
"""Independent completion gate (Tier 1 machine verifier).

Trusts nothing the runner or authoring agent wrote except as claims to re-check:
  Gate 1: every command exit code == 0 (from state, cross-checked against the EXECUTED receipt),
          each required output physically exists and its sha256 matches the hash recorded at execution,
          git SHA recorded is a 40-hex commit that exists in the repo.
  Gate 2: the stored raw packet re-hashes to packet_sha256 and re-validates against the canonical v3
          template; zero secrets in outputs and logs; forbidden paths unchanged and forbidden patterns
          absent; the packet's declared tests, run here by the verifier itself, exit 0.
  Ledger hash chain must verify.
Only if every gate is true does it call Store.complete(). Otherwise status -> VERIFICATION_FAILED.

Usage: python3 -I -m execboundary.verifier --root STATE_DIR --repo GIT_WORKTREE TASK_ID
Exit: 0 PASS (COMPLETE written), 1 FAIL, 2 not verifiable (no such task / wrong state).
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from execboundary import schema
from execboundary.runner import tree_fingerprint
from execboundary.store import LedgerError, Store, now, sha256_file

SECRET_PATTERNS = [re.compile(p) for p in (
    r"gh[pousr]_[A-Za-z0-9]{36,}", r"github_pat_[A-Za-z0-9_]{40,}", r"sk-[A-Za-z0-9_-]{20,}",
    r"sk-ant-[A-Za-z0-9_-]{20,}", r"AKIA[0-9A-Z]{16}", r"AIza[0-9A-Za-z_-]{35}",
    r"xox[baprs]-[A-Za-z0-9-]{10,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"ya29\.[A-Za-z0-9_-]{20,}")]
TEST_TIMEOUT = schema.MAX_TIMEOUT


def scan(paths):
    hits, texts = [], []
    for p in paths:
        try:
            t = Path(p).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        texts.append((str(p), t))
        for rx in SECRET_PATTERNS:
            if rx.search(t):
                hits.append({"file": str(p), "pattern": rx.pattern})
    return hits, texts


def verify(root, repo, task_id):
    store = Store(root)
    repo = Path(repo).resolve()
    st = store.get(task_id)
    if st is None or st["status"] != "PENDING_VERIFICATION":
        return 2, {"error": "task not PENDING_VERIFICATION", "status": st and st["status"]}
    gates, evidence = {}, {}

    # ---- Gate 2a: schema (re-derived from stored bytes, not from the runner's say-so)
    raw_p = store.root / "packets" / (st["packet_sha256"] + ".json")
    env = None
    try:
        raw = raw_p.read_bytes()
        if hashlib.sha256(raw).hexdigest() != st["packet_sha256"]:
            raise schema.Rejected("PACKET_TAMPERED", "stored packet hash mismatch")
        env, _ = schema.validate_envelope(raw)
        gates["schema_valid"] = env["packet"]["task_id"] == task_id
    except (OSError, schema.Rejected) as e:
        gates["schema_valid"] = False
        evidence["schema_error"] = str(e)

    # ---- Gate 1a: exit codes, cross-checked with the EXECUTED receipt
    rdir = store.root / "receipts" / task_id
    executed = [json.loads(p.read_text()) for p in sorted(rdir.glob("*-EXECUTED.json"))]
    last = executed[-1]["data"] if executed else None
    cmds = st.get("commands") or []
    n_expected = len(env["execution"]["commands"]) if env else -1
    gates["exit_code_zero"] = bool(last) and last.get("attempt") == st["attempt"] and \
        len(cmds) == n_expected and all(c.get("exit_code") == 0 for c in cmds) and \
        last.get("commands") == cmds and st.get("exit_code") == 0
    evidence["exit_codes"] = [c.get("exit_code") for c in cmds]

    # ---- Gate 1b: physical outputs, hash at execution == hash now
    outs = {}
    ok = bool(env)
    for rel in (env["execution"]["required_outputs"] if env else []):
        p = repo / rel
        cur = sha256_file(p) if p.is_file() else None
        rec = (st.get("outputs") or {}).get(rel)
        outs[rel] = {"recorded": rec, "current": cur}
        ok = ok and cur is not None and cur == rec
    gates["outputs_exist"] = ok
    evidence["outputs"] = outs

    # ---- Gate 1c: git SHA logged and real
    sha = st.get("git_sha") or ""
    real = bool(re.fullmatch(r"[0-9a-f]{40}", sha)) and subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", sha + "^{commit}"], capture_output=True).returncode == 0
    gates["git_sha_logged"] = real and bool(last) and last.get("git_sha") == sha
    evidence["git_sha"] = sha

    # ---- Gate 2b: secrets in outputs + logs
    logdir = store.root / st.get("log_dir", "__missing__")
    files = [repo / r for r in outs] + (sorted(logdir.glob("*")) if logdir.is_dir() else [])
    hits, texts = scan(files)
    gates["zero_secrets"] = not hits
    evidence["secret_hits"] = hits

    # ---- Gate 2c: negative constraints
    neg = env is not None
    if env:
        fp = tree_fingerprint(repo, schema.effective_forbidden(env))
        unchanged = fp == st.get("forbidden_fingerprint_before")
        bad = [{"file": f, "pattern": pat} for pat in env["execution"]["forbidden_patterns"]
               for f, t in texts if pat in t]
        evidence["forbidden_paths_unchanged"] = unchanged
        evidence["forbidden_pattern_hits"] = bad
        neg = unchanged and not bad
    gates["negative_constraints_met"] = neg

    # ---- Gate 2d: verifier runs the declared tests itself
    test_results = []
    tests_ok = env is not None
    for argv in (env["execution"]["tests"] if env else []):
        try:
            r = subprocess.run(argv, cwd=repo, capture_output=True, timeout=TEST_TIMEOUT, stdin=subprocess.DEVNULL)
            code = r.returncode
            tail = (r.stdout + r.stderr)[-2000:].decode("utf-8", "replace")
        except (subprocess.TimeoutExpired, OSError) as e:
            code, tail = None, str(e)
        test_results.append({"argv": argv, "exit_code": code, "output_tail": tail})
        tests_ok = tests_ok and code == 0
    gates["tests_passed"] = tests_ok
    evidence["tests"] = test_results

    # ---- ledger integrity
    try:
        rows, head = store.verify_chain()
        evidence["ledger"] = {"rows": rows, "head": head, "intact": True}
        ledger_ok = True
    except LedgerError as e:
        evidence["ledger"] = {"intact": False, "error": str(e)}
        ledger_ok = False

    result = "PASS" if ledger_ok and all(gates.values()) else "FAIL"
    verdict = {"verifier": "execboundary.verifier", "verified_at": now(), "task_id": task_id,
               "attempt": st["attempt"], "packet_sha256": st["packet_sha256"], "result": result,
               "gates": gates, "evidence": evidence}
    vpath = store.root / "receipts" / task_id
    store.receipt(task_id, "VERDICT", {"result": result, "gates": gates, "attempt": st["attempt"],
                                       "evidence": evidence})
    if result == "PASS":
        store.complete(task_id, verdict)
        return 0, verdict
    st.update(status="VERIFICATION_FAILED", verification_failed_at=now(),
              failed_gates=[g for g, v in gates.items() if not v] + ([] if ledger_ok else ["ledger_intact"]))
    if st["attempt"] >= schema.MAX_ATTEMPTS:
        st["status"] = "BLOCKER_DISCOVERED"
        store.put(st)
        store.receipt(task_id, "BLOCKER_DISCOVERED", {"reason": "verification failed at attempt limit",
                                                      "failed_gates": st["failed_gates"]})
    else:
        store.put(st)
    return 1, verdict


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("task_id")
    a = ap.parse_args(argv)
    code, verdict = verify(a.root, a.repo, a.task_id)
    sys.stdout.write(json.dumps({"exit": code, "result": verdict.get("result"), "gates": verdict.get("gates"),
                                 "error": verdict.get("error")}, sort_keys=True) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
