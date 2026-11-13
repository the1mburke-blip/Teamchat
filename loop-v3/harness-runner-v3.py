#!/usr/bin/env python3
"""ICARUS harness v3: executes one task packet through the dual gate and appends a receipt.

Contract used by icarus_pilot.py and the CI workflow:
  execute_packet(path) -> {"receipt", "readback", "issue_comment", "appended"}
  verify_ledger()      -> {"ok", "lines", "head_hash", "head_check", "errors"}
  CLI: python3 harness-runner-v3.py --verify-ledger   (exit 0 only when the ledger verifies)

Properties enforced here (Tier 1 machine verifier, never the authoring agent):
  * packet is schema-validated before anything runs (stdlib validator, no extra packages)
  * restricted command scope: python only, no pip/venv, no shell
  * negative constraints are a pre-execution veto and are re-checked against outputs
  * stages never see GITHUB_TOKEN or any other inherited secret (minimal env)
  * secrets in the packet, stdout/stderr or output files block Gate 2 and are redacted
  * attempt cap per stage, wall-clock timeout, and no blind retry (identical failure stops)
  * expected outputs are deleted before each attempt so stale files cannot pass
  * the ledger is append-only (checked against git HEAD) and SHA-256 hash-chained
Receipts are hash-chained here. Signing is done by the workflow (GitHub keyless attestation), not by this file.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

REPO = Path(os.environ.get("ICARUS_REPO_ROOT") or Path(__file__).resolve().parent)
LEDGER_REL = "icarus/runs/RUN_LOG.jsonl"
SCHEMA_REL = "schemas/task_packet.v3.schema.json"
GENESIS = "0" * 64
SHA_RE = re.compile(r"[0-9a-f]{40}")
ALLOWED_EXECUTABLES = {"python3", "python"}
DENIED_MODULES = {"pip", "ensurepip", "venv"}
TAIL = 4000
MAX_SCAN_BYTES = 1_000_000

BUILTIN_FORBIDDEN = [
    ("NC_NO_NOTEBOOK_UI", ["notebooklm", "gemini.google.com", "Gemini Notebook"]),
    ("NC_NO_MAIN_PUSH", ["git push", "push origin main", "HEAD:main"]),
]

SECRET_PATTERNS = [
    re.compile(p)
    for p in [
        r"gh[pousr]_[A-Za-z0-9]{30,}",
        r"github_pat_[A-Za-z0-9_]{20,}",
        r"AKIA[0-9A-Z]{16}",
        r"sk-[A-Za-z0-9_-]{20,}",
        r"xox[baprs]-[A-Za-z0-9-]{10,}",
        r"AIza[0-9A-Za-z_-]{35}",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"(?i)\b(?:api[_-]?key|secret|token|passwd|password)\b\s*[:=]\s*[\"']?[A-Za-z0-9/+_.\-]{16,}",
    ]
]


def utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(body: dict) -> str:
    return hashlib.sha256(_canon(body).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- schema ---
def _type_ok(v, t) -> bool:
    return {
        "string": isinstance(v, str),
        "integer": isinstance(v, int) and not isinstance(v, bool),
        "object": isinstance(v, dict),
        "array": isinstance(v, list),
        "boolean": isinstance(v, bool),
    }.get(t, True)


def validate(inst, schema: dict, path: str = "$") -> list:
    """Validate the JSON-schema subset used by schemas/task_packet.v3.schema.json."""
    t = schema.get("type")
    if t and not _type_ok(inst, t):
        return [f"{path}: expected {t}"]
    errs = []
    if "enum" in schema and inst not in schema["enum"]:
        errs.append(f"{path}: value not in enum {schema['enum']}")
    if isinstance(inst, str):
        if len(inst) < schema.get("minLength", 0):
            errs.append(f"{path}: shorter than minLength {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], inst):
            errs.append(f"{path}: does not match pattern {schema['pattern']}")
    if isinstance(inst, int) and not isinstance(inst, bool):
        if "minimum" in schema and inst < schema["minimum"]:
            errs.append(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and inst > schema["maximum"]:
            errs.append(f"{path}: above maximum {schema['maximum']}")
    if isinstance(inst, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in inst:
                errs.append(f"{path}.{k}: required property missing")
        if schema.get("additionalProperties") is False:
            for k in inst:
                if k not in props:
                    errs.append(f"{path}.{k}: additional property not allowed")
        for k, sub in props.items():
            if k in inst:
                errs += validate(inst[k], sub, f"{path}.{k}")
    if isinstance(inst, list):
        if len(inst) < schema.get("minItems", 0):
            errs.append(f"{path}: fewer than minItems {schema['minItems']}")
        if isinstance(schema.get("items"), dict):
            for i, x in enumerate(inst):
                errs += validate(x, schema["items"], f"{path}[{i}]")
    return errs


# --------------------------------------------------------------- secrets ---
def find_secrets(text: str) -> list:
    return sorted({p.pattern for p in SECRET_PATTERNS if p.search(text or "")})


def redact(text: str) -> str:
    for p in SECRET_PATTERNS:
        text = p.sub("[REDACTED]", text or "")
    return text


# ------------------------------------------------------------------- git ---
def _git(*args, text=True):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=text, timeout=30)


def current_sha() -> str:
    s = os.environ.get("GITHUB_SHA", "")
    if SHA_RE.fullmatch(s):
        return s
    try:
        p = _git("rev-parse", "HEAD")
        s = p.stdout.strip()
        return s if p.returncode == 0 and SHA_RE.fullmatch(s) else ""
    except Exception:
        return ""


# ---------------------------------------------------------------- ledger ---
def ledger_path() -> Path:
    return REPO / LEDGER_REL


def verify_ledger() -> dict:
    errs, prev, n, ids = [], GENESIS, 0, set()
    p = ledger_path()
    data = p.read_bytes() if p.exists() else b""
    if data and not data.endswith(b"\n"):
        errs.append("ledger does not end with a newline")
    for i, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
        if not line.strip():
            errs.append(f"line {i}: blank line")
            continue
        try:
            o = json.loads(line)
        except ValueError:
            errs.append(f"line {i}: invalid JSON")
            continue
        n += 1
        h = o.get("receipt_hash")
        if h != _hash({k: v for k, v in o.items() if k != "receipt_hash"}):
            errs.append(f"line {i}: receipt_hash does not match content")
        if o.get("prev_receipt_hash") != prev:
            errs.append(f"line {i}: hash chain broken")
        if o.get("run_id") in ids:
            errs.append(f"line {i}: duplicate run_id")
        ids.add(o.get("run_id"))
        prev = h or prev
    head = "NO_GIT"
    try:
        inside = _git("rev-parse", "--is-inside-work-tree")
        if inside.returncode == 0 and inside.stdout.strip() == "true":
            # "./" makes the path relative to REPO, so the harness also works from a subdirectory
            if _git("cat-file", "-e", f"HEAD:./{LEDGER_REL}").returncode == 0:
                committed = _git("show", f"HEAD:./{LEDGER_REL}", text=False).stdout
                if data.startswith(committed):
                    head = "OK"
                else:
                    head = "MISMATCH"
                    errs.append("ledger is not an append-only extension of git HEAD")
            else:
                head = "UNTRACKED_AT_HEAD"
    except Exception as e:  # git missing or timed out: report, do not guess
        head = f"SKIPPED:{type(e).__name__}"
    return {"ok": not errs, "lines": n, "head_hash": prev, "head_check": head, "errors": errs}


def _append_receipt(receipt: dict) -> None:
    p = ledger_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "ab") as fh:
        fh.write((_canon(receipt) + "\n").encode("utf-8"))
        fh.flush()
        os.fsync(fh.fileno())


# ----------------------------------------------------------------- policy ---
def command_scope_violations(packet: dict) -> list:
    out = []
    for st in packet["stages"]:
        cmd = st["command"]
        exe = os.path.basename(cmd[0])
        if exe not in ALLOWED_EXECUTABLES:
            out.append(f"{st['stage_id']}: executable '{exe}' not allowed (python only)")
        for i, a in enumerate(cmd[:-1]):
            if a == "-m" and cmd[i + 1] in DENIED_MODULES:
                out.append(f"{st['stage_id']}: module '{cmd[i + 1]}' not allowed")
    return out


def negative_constraint_violations(packet: dict, texts: dict) -> list:
    """texts maps a label to the text to scan (commands pre-run; outputs post-run)."""
    rules = list(BUILTIN_FORBIDDEN) + [
        (c["id"], c["forbidden_patterns"]) for c in packet.get("negative_constraints", [])
    ]
    out = []
    for rid, pats in rules:
        for label, text in texts.items():
            for pat in pats:
                if pat.lower() in text.lower():
                    out.append(f"{rid}: '{pat}' found in {label}")
    return out


def _stage_env(run_id: str, task_id: str, stage_id: str) -> dict:
    keep = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env.update(ICARUS_RUN_ID=run_id, ICARUS_TASK_ID=task_id, ICARUS_STAGE_ID=stage_id)
    if os.environ.get("GITHUB_SHA"):
        env["GITHUB_SHA"] = os.environ["GITHUB_SHA"]
    return env  # GITHUB_TOKEN and every other inherited variable are deliberately excluded


# ----------------------------------------------------------------- stages ---
def _s(s) -> str:
    return s.decode("utf-8", "replace") if isinstance(s, bytes) else (s or "")


def _tail(s) -> str:
    return redact(_s(s)[-TAIL:])


def _within_artifacts(rel: str) -> bool:
    try:
        return (REPO / rel).resolve().is_relative_to((REPO / "icarus/runs/artifacts").resolve())
    except Exception:
        return False


def run_stage(stage: dict, run_id: str, task_id: str) -> dict:
    attempts, prev_sig, ok = [], None, False
    outs = stage["expected_outputs"]
    for n in range(1, stage["attempt_limit"] + 1):
        for rel in outs:  # stale outputs must not satisfy this attempt
            if _within_artifacts(rel) and (REPO / rel).is_file():
                (REPO / rel).unlink()
        t0 = datetime.datetime.now(datetime.timezone.utc)
        timed_out, rc, out, err = False, None, "", ""
        try:
            p = subprocess.run(
                stage["command"], cwd=REPO, env=_stage_env(run_id, task_id, stage["stage_id"]),
                capture_output=True, text=True, timeout=stage["timeout_seconds"],
            )
            rc, out, err = p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired as e:
            timed_out, out, err = True, e.stdout or "", e.stderr or ""
        except OSError as e:
            err = f"{type(e).__name__}: {e}"
        missing = [r for r in outs if not (_within_artifacts(r) and (REPO / r).is_file())]
        dur = round((datetime.datetime.now(datetime.timezone.utc) - t0).total_seconds(), 3)
        ok = rc == 0 and not timed_out and not missing
        attempts.append({
            "attempt": n, "exit_code": rc, "timed_out": timed_out, "duration_s": dur,
            "missing_outputs": missing, "stdout_tail": _tail(out), "stderr_tail": _tail(err),
            "secret_hits": len(find_secrets(_s(out) + _s(err))),  # counted on raw output, before redaction
        })
        if ok:
            break
        sig = (rc, timed_out, tuple(missing), hashlib.sha256((_tail(err)).encode()).hexdigest())
        if sig == prev_sig:
            attempts[-1]["stopped"] = "identical failure signature; blind retry prohibited"
            break
        prev_sig = sig
    return {"stage_id": stage["stage_id"], "name": stage["name"], "ok": ok,
            "attempt_limit": stage["attempt_limit"], "attempts": attempts}


# ----------------------------------------------------------- issue comment ---
def post_dispatch_comment(receipt: dict) -> dict:
    """Optional receipt comment on an EXISTING issue. Never creates issues.

    Needs GITHUB_TOKEN, GITHUB_REPOSITORY and ICARUS_DISPATCH_ISSUE. The Teamchat workflow does not set
    ICARUS_DISPATCH_ISSUE: it posts one comment from receipt_comment.py after signing instead.
    """
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    num = os.environ.get("ICARUS_DISPATCH_ISSUE", "")
    if not (token and repo and num.isdigit()):
        return {"attempted": False, "reason": "GITHUB_TOKEN/GITHUB_REPOSITORY/ICARUS_DISPATCH_ISSUE not all set"}
    g1, g2 = receipt["gate_1_technical"], receipt["gate_2_policy"]
    body = (f"**{receipt['status']}** `{receipt['task_id']}` run `{receipt['run_id']}`\n"
            f"- Gate 1 passed: {g1['passed']}, Gate 2 passed: {g2['passed']}\n"
            f"- git SHA: `{receipt['git_sha']}`\n- receipt_hash: `{receipt['receipt_hash']}`\n"
            f"- verifier: {receipt['verifier_tier']} (hash-chained, not signed by this step)\n")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues/{num}/comments", method="POST",
        data=json.dumps({"body": body}).encode(),
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "User-Agent": "icarus-harness-v3", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return {"attempted": True, "ok": True, "url": json.loads(r.read().decode()).get("html_url")}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"attempted": True, "ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}


# ---------------------------------------------------------------- execute ---
def _readback(receipt: dict) -> dict:
    v = verify_ledger()
    found = None
    p = ledger_path()
    if p.exists():
        for line in p.read_text("utf-8", "replace").splitlines():
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if o.get("run_id") == receipt["run_id"]:
                found = o
    arts_ok = all(
        (REPO / a["path"]).is_file() and _sha256_file(REPO / a["path"]) == a["sha256"]
        for a in receipt["artifacts"]
    )
    return {
        "ledger_line_found": found is not None,
        "receipt_hash_matches": bool(found) and found.get("receipt_hash") == receipt["receipt_hash"],
        "artifacts_rehashed_ok": arts_ok,
        "ledger_verify_ok": v["ok"], "ledger_lines": v["lines"], "head_check": v["head_check"],
    }


def execute_packet(packet_path) -> dict:
    packet_path = Path(packet_path)
    started = utcnow()
    raw = packet_path.read_bytes()
    try:
        packet = json.loads(raw)
    except ValueError:
        packet = None
    schema = json.loads((REPO / SCHEMA_REL).read_text("utf-8"))
    schema_errors = ["packet is not valid JSON"] if packet is None else validate(packet, schema)
    schema_valid = not schema_errors
    task_id = packet.get("task_id") if isinstance(packet, dict) and isinstance(packet.get("task_id"), str) else "UNKNOWN"
    run_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]

    packet_secrets = find_secrets(raw.decode("utf-8", "replace"))
    scope_viol, nc_viol, pre = [], [], {"ledger_ok": True}
    stages_out, artifacts, run_secrets = [], [], []
    if schema_valid:
        scope_viol = command_scope_violations(packet)
        nc_viol = negative_constraint_violations(
            packet, {f"command {s['stage_id']}": " ".join(s["command"]) for s in packet["stages"]})
    pre_ledger = verify_ledger()
    pre["ledger_ok"], pre["ledger_errors"] = pre_ledger["ok"], pre_ledger["errors"]
    vetoed = (not schema_valid) or scope_viol or nc_viol or packet_secrets or not pre_ledger["ok"]

    all_stages_ok = False
    if not vetoed:
        all_stages_ok = True
        for st in packet["stages"]:
            if not all_stages_ok:
                stages_out.append({"stage_id": st["stage_id"], "name": st["name"], "ok": False,
                                   "attempts": [], "skipped": "earlier stage failed"})
                continue
            res = run_stage(st, run_id, task_id)
            stages_out.append(res)
            all_stages_ok = res["ok"]
        texts = {}
        for res in stages_out:
            for a in res["attempts"]:
                texts[f"{res['stage_id']} stdout"] = a["stdout_tail"]
        for st in packet["stages"]:
            for rel in st["expected_outputs"]:
                f = REPO / rel
                if _within_artifacts(rel) and f.is_file():
                    body = f.read_bytes()[:MAX_SCAN_BYTES].decode("utf-8", "replace")
                    texts[f"output {rel}"] = body
                    hits = find_secrets(body)
                    run_secrets += hits
                    if hits:  # never leave a secret in a file CI will commit
                        f.write_text(redact(f.read_bytes().decode("utf-8", "replace")), "utf-8")
                    artifacts.append({"path": rel, "sha256": _sha256_file(f), "bytes": f.stat().st_size,
                                      **({"redacted": True} if hits else {})})
        run_secrets += ["stage-output-secret"] * sum(
            a["secret_hits"] for r in stages_out for a in r["attempts"])
        nc_viol += [v for v in negative_constraint_violations(packet, texts) if v not in nc_viol]
    sha = current_sha()
    exit_ok = bool(stages_out) and all_stages_ok and all(
        r["attempts"] and r["attempts"][-1]["exit_code"] == 0 for r in stages_out)
    outputs_ok = bool(artifacts) and all(
        (REPO / rel).is_file() for st in (packet["stages"] if schema_valid else []) for rel in st["expected_outputs"])
    if schema_valid and not any(st["expected_outputs"] for st in packet["stages"]):
        outputs_ok = False
    g1 = {"exit_code_zero": exit_ok, "physical_output_files_exist": outputs_ok,
          "git_sha_logged": bool(sha), "git_sha": sha}
    g1["passed"] = exit_ok and outputs_ok and bool(sha)
    secret_hits = sorted(set(packet_secrets + run_secrets))
    g2 = {"schema_valid": schema_valid, "schema_errors": schema_errors[:20],
          "zero_secrets_detected": not secret_hits, "secret_pattern_hits": len(secret_hits),
          "negative_constraints_met": not nc_viol, "negative_constraint_violations": nc_viol,
          "command_scope_ok": not scope_viol, "command_scope_violations": scope_viol}
    g2["passed"] = schema_valid and not secret_hits and not nc_viol and not scope_viol
    if vetoed or not g2["passed"]:
        status = "BLOCKED"
    elif g1["passed"]:
        status = "PASS"
    else:
        status = "FAIL"
    receipt = {
        "schema": "icarus/receipt.v3", "run_id": run_id, "task_id": task_id,
        "packet_file": packet_path.name, "packet_sha256": hashlib.sha256(raw).hexdigest(),
        "started_at": started, "finished_at": utcnow(), "status": status,
        "verifier_tier": "TIER_1_MACHINE", "signed": False,
        "gate_1_technical": g1, "gate_2_policy": g2, "pre_execution": pre,
        "stages": stages_out, "artifacts": artifacts, "git_sha": sha,
        "prev_receipt_hash": pre_ledger["head_hash"],
    }
    receipt["receipt_hash"] = _hash(receipt)
    appended = False
    if pre_ledger["ok"]:
        _append_receipt(receipt)
        appended = True
    readback = _readback(receipt) if appended else {"ledger_line_found": False, "reason": "ledger failed precheck; nothing appended"}
    comment = post_dispatch_comment(receipt)
    return {"receipt": receipt, "readback": readback, "issue_comment": comment, "appended": appended}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--verify-ledger" in argv:
        v = verify_ledger()
        print(json.dumps(v, indent=2))
        return 0 if v["ok"] else 1
    if len(argv) == 2 and argv[0] == "--run":
        r = execute_packet(argv[1])
        print(json.dumps(r, indent=2))
        return 0 if r["receipt"]["status"] == "PASS" and r["appended"] else 1
    print("usage: harness-runner-v3.py --verify-ledger | --run PACKET.json", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
