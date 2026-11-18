"""Positive and negative tests for the external execution boundary (execboundary/)."""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from execboundary import canary, schema
from execboundary.runner import Runner
from execboundary.store import LedgerError, Store
from execboundary.verifier import verify

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def env(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "GOAL.md").write_text("goal\n")
    for args in (["init", "-q"], ["add", "."], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
        subprocess.run(["git", "-C", str(repo)] + args, check=True)
    root = tmp_path / "state"
    return Runner(root, repo), repo, root


def drop(root, name, data):
    p = Path(root) / "inbox" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data if isinstance(data, bytes) else canary.dump(data))


def receipts(root, task_id):
    return [p.name.split("-", 1)[1][:-5] for p in sorted((Path(root) / "receipts" / task_id).glob("*.json"))]


# ---------------- positive ----------------

def test_canary_reaches_complete_only_via_verifier(env):
    r, repo, root = env
    drop(root, "c1.json", canary.envelope("CANARY-1", "out/c1.txt"))
    r.cycle()
    st = r.store.get("CANARY-1")
    assert st["status"] == "COMPLETE", st
    assert receipts(root, "CANARY-1") == ["VALIDATED", "CLAIMED", "EXECUTED", "VERDICT", "COMPLETE"]
    verdict = json.loads(sorted((root / "receipts" / "CANARY-1").glob("*-VERDICT.json"))[0].read_text())
    assert verdict["data"]["result"] == "PASS" and all(verdict["data"]["gates"].values())
    assert len(st["git_sha"]) == 40
    r.store.verify_chain()
    assert not list((root / "inbox").iterdir())


def test_issue_241_packet_itself_validates():
    body = (REPO_ROOT / "execboundary" / "fixtures" / "issue-241-packet.json").read_bytes()
    pkt = schema.parse(body)
    schema.validate_packet(pkt, schema.load_json(schema.DEFAULT_TEMPLATE))


# ---------------- ingress rejections ----------------

def _mut(fn):
    e = canary.envelope("BAD", "out/bad.txt")
    fn(e)
    return e


BAD = {
    "malformed_json": b"{not json",
    "duplicate_key": b'{"envelope_version":"execboundary/1","envelope_version":"x"}',
    "missing_field": _mut(lambda e: e["packet"].pop("objective")),
    "unknown_field": _mut(lambda e: e["execution"].update(sudo=True)),
    "rules_weakened": _mut(lambda e: e["packet"]["immutable_execution_rules"]["rule_4_solution_discovery_loop"].update(max_attempts_per_agent=99)),
    "attempt_limit_4": _mut(lambda e: e["packet"]["stages_to_execute"][0].update(attempt_limit=4)),
    "timeout_301": _mut(lambda e: e["packet"]["stages_to_execute"][0].update(timeout_seconds=301)),
    "placeholder": _mut(lambda e: e["packet"].update(objective="{{OBJECTIVE}}")),
    "unauthorized": _mut(lambda e: e["execution"].update(authorized_by="Mallory")),
    "shell_string": _mut(lambda e: e["execution"].update(commands=["rm -rf /"])),
    "path_escape": _mut(lambda e: e["execution"].update(required_outputs=["../x"])),
    "protected_output": _mut(lambda e: e["execution"].update(required_outputs=["icarus/core/x.py"])),
    "wrong_version": _mut(lambda e: e["packet"].update(template_version="v2.0.0")),
    "gate_altered": _mut(lambda e: e["packet"]["adjudication"].update(gate_2_policy_compliance="true")),
}


@pytest.mark.parametrize("name", sorted(BAD))
def test_malformed_or_unauthorized_never_executes(env, name):
    r, repo, root = env
    drop(root, name + ".json", BAD[name])
    r.cycle()
    assert r.store.get("BAD") is None
    assert not (repo / "out").exists()
    assert receipts(root, "_ingress") == ["REJECTED"]
    assert len(list((root / "rejected").iterdir())) == 1


# ---------------- completion gate negatives ----------------

def test_failed_command_cannot_complete(env):
    r, repo, root = env
    drop(root, "f.json", canary.envelope("FAIL-1", "out/f.txt", extra_cmd=["python3", "-c", "raise SystemExit(7)"]))
    r.cycle()
    st = r.store.get("FAIL-1")
    assert st["status"] == "FAILED" and st["exit_code"] == 7
    assert "COMPLETE" not in receipts(root, "FAIL-1")


def test_failed_test_cannot_complete(env):
    r, repo, root = env
    drop(root, "t.json", canary.envelope("TEST-1", "out/t.txt", tests=[["python3", "-c", "raise SystemExit(1)"]]))
    r.cycle()
    st = r.store.get("TEST-1")
    assert st["status"] == "VERIFICATION_FAILED" and st["failed_gates"] == ["tests_passed"]


def test_secret_in_output_blocks(env):
    r, repo, root = env
    drop(root, "s.json", canary.envelope("SEC-1", "out/s.txt", content="token ghp_" + "a" * 36))
    r.cycle()
    assert r.store.get("SEC-1")["failed_gates"] == ["zero_secrets"]


def test_forbidden_path_change_blocks(env):
    r, repo, root = env
    drop(root, "n.json", canary.envelope("NEG-1", "out/n.txt",
                                         extra_cmd=["python3", "-c", "open('GOAL.md','a').write('x')"]))
    r.cycle()
    assert r.store.get("NEG-1")["failed_gates"] == ["negative_constraints_met"]


def test_output_tampered_after_execution_blocks(env):
    r, repo, root = env
    r.spawn_verifier = False
    drop(root, "o.json", canary.envelope("TAMP-1", "out/o.txt"))
    r.cycle()
    (repo / "out" / "o.txt").write_text("changed")
    code, v = verify(root, repo, "TAMP-1")
    assert code == 1 and v["gates"]["outputs_exist"] is False


def test_store_refuses_complete_without_verifier_verdict(env):
    r, repo, root = env
    r.spawn_verifier = False
    drop(root, "x.json", canary.envelope("SELF-1", "out/x.txt"))
    r.cycle()
    st = r.store.get("SELF-1")
    with pytest.raises(LedgerError):
        r.store.put(dict(st, status="COMPLETE"))
    forged = {"verifier": "claude", "result": "PASS", "gates": {}, "packet_sha256": st["packet_sha256"], "attempt": 1}
    with pytest.raises(LedgerError):
        r.store.complete("SELF-1", forged)
    gates = dict.fromkeys(["exit_code_zero", "outputs_exist", "git_sha_logged", "schema_valid",
                           "zero_secrets", "negative_constraints_met"], True)
    gates["tests_passed"] = False
    with pytest.raises(LedgerError):
        r.store.complete("SELF-1", dict(forged, verifier="execboundary.verifier", gates=gates))
    assert r.store.get("SELF-1")["status"] == "PENDING_VERIFICATION"


# ---------------- attempts, retries, ledger ----------------

def test_blind_retry_rejected_and_three_attempt_cap(env):
    r, repo, root = env
    bad = lambda n: canary.envelope("CAP-1", "out/cap.txt", extra_cmd=["python3", "-c", "raise SystemExit(%d)" % n])
    drop(root, "a.json", bad(1)); r.cycle()
    drop(root, "a2.json", bad(1)); r.cycle()          # identical packet -> BLIND_RETRY
    assert r.store.get("CAP-1")["attempt"] == 1
    drop(root, "b.json", bad(2)); r.cycle()
    drop(root, "c.json", bad(3)); r.cycle()
    st = r.store.get("CAP-1")
    assert st["attempt"] == 3 and st["status"] == "BLOCKER_DISCOVERED"
    drop(root, "d.json", bad(4)); r.cycle()
    assert r.store.get("CAP-1")["attempt"] == 3
    rec = receipts(root, "CAP-1")
    assert rec.count("REJECTED") == 2 and "BLOCKER_DISCOVERED" in rec


def test_ledger_tamper_detected(env):
    r, repo, root = env
    drop(root, "l.json", canary.envelope("LED-1", "out/l.txt"))
    r.cycle()
    lines = (root / "ledger.jsonl").read_text().splitlines()
    lines[0] = lines[0].replace("VALIDATED", "VALIDATEX")
    (root / "ledger.jsonl").write_text("\n".join(lines) + "\n")
    with pytest.raises(LedgerError):
        Store(root).verify_chain()


def test_absent_capability_reports_blocked(tmp_path):
    from execboundary.runner import main
    assert main(["--root", str(tmp_path / "s"), "--repo", str(tmp_path), "--once"]) == 3


# ---------------- interruption + restart recovery (real processes) ----------------

def test_kill_mid_execution_then_restart_recovers(env):
    r, repo, root = env
    drop(root, "slow.json", canary.envelope("REC-1", "out/rec.txt", sleep=6))
    cmd = [sys.executable, "-m", "execboundary.runner", "--root", str(root), "--repo", str(repo), "--loop", "--interval", "0.5"]
    p = subprocess.Popen(cmd, cwd=REPO_ROOT, start_new_session=True)
    for _ in range(100):
        st = Store(root).get("REC-1")
        if st and st["status"] == "RUNNING":
            break
        time.sleep(0.1)
    assert st["status"] == "RUNNING"
    os.killpg(p.pid, signal.SIGKILL)
    p.wait()
    assert Store(root).get("REC-1")["status"] == "RUNNING"   # stale: executor is dead
    subprocess.run(cmd[:-3] + ["--once"], cwd=REPO_ROOT, check=True, timeout=120)
    st = Store(root).get("REC-1")
    assert st["status"] == "COMPLETE" and st["attempt"] == 2
    assert receipts(root, "REC-1") == ["VALIDATED", "CLAIMED", "INTERRUPTED", "CLAIMED", "EXECUTED", "VERDICT", "COMPLETE"]
