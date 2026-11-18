#!/usr/bin/env python3
"""Independent completion gate (Tier 1 machine). COMPLETE is decided here, never by the authoring agent.

verify_completion() re-derives every fact from disk instead of trusting the runner's in-memory result:
  exit code 0 on every stage, required outputs exist and re-hash to the receipt, git SHA recorded,
  packet re-validates against the v3 schema, zero secrets in packet/outputs/logs, negative constraints
  hold, ledger hash chain intact, attempt cap respected, receipt in the ledger matches the state record.
CLI:  completion_gate.py --audit      re-verify every state file that claims COMPLETE (exit 0 only if all hold)
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHA_RE = re.compile(r"[0-9a-f]{40}")
MAX_ATTEMPTS = 3


def load_harness(repo: Path):
    spec = importlib.util.spec_from_file_location("harness_runner_v3", HERE / "harness-runner-v3.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.REPO = repo
    return mod


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_packet(repo: Path, state: dict):
    for rel in (state.get("packet_path"), f"task_queue/{state.get('packet_file')}"):
        if rel and (repo / rel).is_file():
            return repo / rel
    return None


def verify_completion(repo: Path, state: dict, harness=None) -> dict:
    h = harness or load_harness(repo)
    checks, errors = {}, []

    def chk(name, ok, why=""):
        checks[name] = bool(ok)
        if not ok:
            errors.append(f"{name}: {why}" if why else name)

    chk("attempts_within_cap", 1 <= int(state.get("attempts", 0)) <= MAX_ATTEMPTS, f"attempts={state.get('attempts')}")
    chk("recorded_exit_status_zero", state.get("exit_status") == 0, f"exit_status={state.get('exit_status')}")
    chk("git_sha_recorded", bool(SHA_RE.fullmatch(state.get("source_sha") or "")), "source_sha missing/invalid")

    ppath = _find_packet(repo, state)
    raw, packet = b"", None
    if ppath is None:
        chk("packet_present", False, "packet file not found")
    else:
        raw = ppath.read_bytes()
        chk("packet_hash_matches_state", hashlib.sha256(raw).hexdigest() == state.get("packet_sha256"), "packet changed since claim")
        try:
            packet = json.loads(raw)
        except ValueError:
            packet = None
        schema = json.loads((repo / h.SCHEMA_REL).read_text("utf-8"))
        errs = ["packet is not valid JSON"] if packet is None else h.validate(packet, schema)
        chk("schema_valid", not errs, "; ".join(errs[:3]))
        chk("zero_secrets_in_packet", not h.find_secrets(raw.decode("utf-8", "replace")), "secret pattern in packet")

    ledger = h.verify_ledger()
    chk("ledger_chain_valid", ledger["ok"], "; ".join(ledger["errors"][:3]))
    rec = None
    lp = h.ledger_path()
    if lp.exists():
        for line in lp.read_text("utf-8", "replace").splitlines():
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if o.get("run_id") == state.get("run_id") and o.get("schema") == "icarus/receipt.v3":
                rec = o
    chk("execution_receipt_in_ledger", rec is not None, "no receipt for run_id")
    if rec:
        chk("receipt_hash_matches_state", rec.get("receipt_hash") == state.get("receipt_hash"), "receipt_hash differs")
        chk("receipt_status_pass", rec.get("status") == "PASS", f"status={rec.get('status')}")
        chk("gate_1_passed", rec["gate_1_technical"].get("passed") is True, "gate_1 not passed")
        chk("gate_2_passed", rec["gate_2_policy"].get("passed") is True, "gate_2 not passed")
        chk("receipt_git_sha_matches", rec.get("git_sha") == state.get("source_sha") and bool(SHA_RE.fullmatch(rec.get("git_sha") or "")), "git sha mismatch")
        stages = rec.get("stages") or []
        chk("every_stage_exit_zero", bool(stages) and all(
            s.get("ok") and s.get("attempts") and s["attempts"][-1].get("exit_code") == 0
            and not s["attempts"][-1].get("timed_out") for s in stages), "a stage did not exit 0")
        arts = rec.get("artifacts") or []
        chk("outputs_exist_and_rehash", bool(arts) and all(
            (repo / a["path"]).is_file() and _sha256(repo / a["path"]) == a["sha256"] for a in arts), "output missing or hash differs")
        texts = {}
        for a in arts:
            f = repo / a["path"]
            if f.is_file():
                body = f.read_bytes()[: h.MAX_SCAN_BYTES].decode("utf-8", "replace")
                texts[f"output {a['path']}"] = body
        chk("zero_secrets_in_outputs", not any(h.find_secrets(t) for t in texts.values()), "secret pattern in output")
        if packet is not None and "schema_valid" in checks and checks["schema_valid"]:
            texts.update({f"command {s['stage_id']}": " ".join(s["command"]) for s in packet["stages"]})
            nc = h.negative_constraint_violations(packet, texts)
            chk("negative_constraints_hold", not nc, "; ".join(nc[:3]))
    logp = state.get("log_path")
    if logp and (repo / logp).is_file():
        chk("zero_secrets_in_log", not h.find_secrets((repo / logp).read_text("utf-8", "replace")), "secret pattern in log")
    else:
        chk("zero_secrets_in_log", False, "log file missing")
    return {"ok": all(checks.values()), "checks": checks, "errors": errors}


def audit(repo: Path) -> dict:
    h = load_harness(repo)
    results = {}
    sd = repo / "state"
    for f in sorted(sd.glob("*.json")) if sd.is_dir() else []:
        st = json.loads(f.read_text("utf-8"))
        if st.get("state") == "COMPLETE":
            v = verify_completion(repo, st, h)
            results[st["task_id"]] = v
    return {"ok": all(v["ok"] for v in results.values()), "complete_states": len(results), "results": results}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    repo = Path(os.environ.get("ICARUS_REPO_ROOT") or HERE)
    if "--audit" in argv:
        a = audit(repo)
        print(json.dumps(a, indent=2))
        return 0 if a["ok"] else 1
    print("usage: completion_gate.py --audit", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
