"""CLI contract checks for the evidence gate; no network or provider calls."""
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
