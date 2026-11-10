"""CLI contract checks for the evidence gate; no network or provider calls."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


RUNNER = Path(__file__).resolve().parents[1] / "harness-runner.py"


@pytest.fixture
def packet(tmp_path):
    artifact = tmp_path / "proof.txt"
    return {
        "task_id": "HV-GATE-001", "cost_tier": "LOW",
        "decision_changing": True, "owner_preauthorized": True,
        "command": [sys.executable, "-c",
                    "from pathlib import Path; Path('proof.txt').write_bytes(b'proof')"],
        "readback": {"type": "file_hash", "path": str(artifact),
                     "expected_hash": hashlib.sha256(b"proof").hexdigest()},
    }


def invoke(packet, tmp_path, expected):
    result = subprocess.run(
        [sys.executable, str(RUNNER)], input=json.dumps(packet),
        text=True, capture_output=True, cwd=tmp_path, timeout=15,
    )
    assert result.returncode == expected, result.stderr
    if expected:
        assert result.stdout == ""
    return result


def test_physical_hash_pass(packet, tmp_path):
    result = invoke(packet, tmp_path, 0)
    assert json.loads(result.stdout) == {
        "evaluator": "CHAIR_JUDGE", "task_id": "HV-GATE-001",
        "verdict": "PASS", "proof_artifact": str(tmp_path / "proof.txt"),
        "readback_status": "VERIFIED",
    }
    assert result.stderr == ""


@pytest.mark.parametrize("mutation", [
    {"decision_changing": False}, {"decision_changing": 1},
    {"cost_tier": "UNKNOWN"}, {"command": []}, {"task_id": None},
    {"owner_preauthorized": "true"}, {"unknown": "reject"},
])
def test_invalid_packet_cannot_execute(packet, tmp_path, mutation):
    packet.update(mutation)
    result = invoke(packet, tmp_path, 2)
    assert json.loads(result.stderr)["verdict"] == "HALT_ZERO_VALUE"
    assert not (tmp_path / "proof.txt").exists()


def test_unauthorized_command_cannot_execute(packet, tmp_path):
    packet["owner_preauthorized"] = False
    result = invoke(packet, tmp_path, 3)
    assert len(result.stderr.splitlines()) == 2
    assert result.stderr.startswith("OWNER ASSISTANCE REQUIRED — ")
    assert not (tmp_path / "proof.txt").exists()


def test_failed_command_cannot_forge_pass(packet, tmp_path):
    packet["command"] = [sys.executable, "-c",
                         "import sys; print('DONE'); print('PASS'); sys.exit(9)"]
    result = invoke(packet, tmp_path, 1)
    evidence = json.loads(result.stderr)
    assert evidence["verdict"] == "FAIL"
    assert evidence["execution"]["exit_code"] == 9
    assert "DONE" in evidence["execution"]["stdout"]["text"]


@pytest.mark.parametrize("mode", ["missing", "wrong_hash"])
def test_zero_exit_without_matching_artifact_fails(packet, tmp_path, mode):
    if mode == "missing":
        packet["command"] = [sys.executable, "-c", "pass"]
    else:
        packet["readback"]["expected_hash"] = "0" * 64
    assert json.loads(invoke(packet, tmp_path, 1).stderr)["verdict"] == "FAIL"


def test_missing_executable_escalates(packet, tmp_path):
    packet["command"] = [str(tmp_path / "missing-executable")]
    result = invoke(packet, tmp_path, 3)
    assert len(result.stderr.splitlines()) == 2
    assert result.stderr.startswith("OWNER ASSISTANCE REQUIRED — ")


@pytest.mark.parametrize("explicit", [True, False])
def test_zero_tool_receipt_rejected_even_with_valid_physical_artifact(packet, tmp_path, explicit):
    trace = tmp_path / "trace.json"
    trace.write_text(json.dumps({"task_id": packet["task_id"], "tools_executed": 0,
                                 "tool_events": [], "model_calls": 1,
                                 "verdict": "PASS", "readback_status": "VERIFIED"}))
    packet["execution_receipt"] = str(trace)
    if explicit:
        packet["requires_tools"] = True
    result = invoke(packet, tmp_path, 1)
    assert json.loads(result.stderr)["reason"] == "ZERO_TOOL_EXECUTION_REJECTED"
    assert (tmp_path / "proof.txt").exists(), "real command/artifact do not excuse an empty agent trace"


@pytest.mark.parametrize("rows,expected", [
    ([{"id": "row-1", "result": "proof"}], 0),
    ([{"id": "other", "result": "proof"}], 1),
    ([{"id": "row-1"}], 1),
    ([{"id": "row-1", "result": "proof"}] * 2, 1),
])
def test_ledger_physical_readback(packet, tmp_path, rows, expected):
    payload = "".join(json.dumps(row) + "\n" for row in rows)
    packet["command"] = [sys.executable, "-c",
                         "from pathlib import Path; Path('ledger.jsonl').write_text(" + repr(payload) + ")"]
    packet["readback"] = {
        "type": "ledger_row", "path": str(tmp_path / "ledger.jsonl"),
        "row_id": "row-1", "required_fields": ["id", "result"],
    }
    result = invoke(packet, tmp_path, expected)
    if expected == 0:
        assert json.loads(result.stdout)["readback_status"] == "VERIFIED"


@pytest.fixture
def supervised_route(packet, tmp_path):
    attempts = tmp_path / "attempts"
    attempts.mkdir()
    return {
        "task": packet,
        "target_chair": "CODEX",
        "seat_availability": dict.fromkeys(("CODEX", "SOL", "LUNA", "GRACE"), "unavailable"),
        "availability_expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        "allow_pilot": True,
    }


def invoke_route(route, tmp_path):
    return subprocess.run(
        [sys.executable, str(RUNNER), "--route-task", "-", str(tmp_path / "attempts")],
        input=json.dumps(route), text=True, capture_output=True, cwd=tmp_path, timeout=15,
    )


def test_available_specialist_routes_before_pilot(supervised_route, tmp_path):
    supervised_route["seat_availability"]["CODEX"] = "available"
    result = invoke_route(supervised_route, tmp_path)
    assert result.returncode == 4
    assert json.loads(result.stdout) == {
        "task_id": "HV-GATE-001", "route": "DELEGATE", "target_chair": "CODEX",
    }
    assert not (tmp_path / "proof.txt").exists()
    assert not list((tmp_path / "attempts").iterdir())


@pytest.mark.parametrize("status", ["unknown", "available"])
def test_pilot_waits_when_any_seat_is_unresolved_or_available(supervised_route, tmp_path, status):
    supervised_route["seat_availability"]["GRACE"] = status
    result = invoke_route(supervised_route, tmp_path)
    assert result.returncode == 3
    assert "All specialist seats must be confirmed unavailable" in result.stderr
    assert not (tmp_path / "proof.txt").exists()
    assert not list((tmp_path / "attempts").iterdir())


@pytest.mark.parametrize("changes, code", [
    ({"allow_pilot": False}, 3),
    ({"availability_expires_at": "2000-01-01T00:00:00Z"}, 3),
    ({"availability_expires_at": "2000-01-01+00:00"}, 2),
    ({"seat_availability": {"CODEX": "unavailable"}}, 2),
])
def test_pilot_rejects_unapproved_or_invalid_routing(supervised_route, tmp_path, changes, code):
    supervised_route.update(changes)
    result = invoke_route(supervised_route, tmp_path)
    assert result.returncode == code
    assert not (tmp_path / "proof.txt").exists()
    assert not list((tmp_path / "attempts").iterdir())


@pytest.mark.parametrize("matches", [True, False])
def test_pilot_records_physical_evidence_and_never_repeats(supervised_route, tmp_path, matches):
    task = supervised_route["task"]
    if not matches:
        task["readback"]["expected_hash"] = "0" * 64
    result = invoke_route(supervised_route, tmp_path)
    assert result.returncode == (0 if matches else 1), result.stderr
    if matches:
        evidence = json.loads(result.stdout)
        assert evidence["verdict"] == "VERIFYING"
        assert evidence["exit_code"] == 0
        assert evidence["sha256"] == hashlib.sha256((tmp_path / "proof.txt").read_bytes()).hexdigest()
    else:
        assert "SHA-256 mismatch" in result.stderr
        assert not result.stdout
    (tmp_path / "proof.txt").unlink()
    result = invoke_route(supervised_route, tmp_path)
    assert result.returncode == 3
    assert "Harness Pilot attempt already reserved" in result.stderr
    assert not (tmp_path / "proof.txt").exists()
    marker, = (tmp_path / "attempts").iterdir()
    assert json.loads(marker.read_text())["task_id"] == task["task_id"]
