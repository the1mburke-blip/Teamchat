"""Offline dispatcher/receipt regressions, including the public CLI boundary."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from dsh.execution_integrity import ExecutionRejected, validate_execution


ROOT = Path(__file__).resolve().parents[1]
TASK = {"task_id": "autonomy-negative", "requires_tools": True,
        "requires_state_mutation": False}


def receipt(count=0, events=None):
    return {"task_id": TASK["task_id"], "tools_executed": count,
            "tool_events": events or [], "readback_status": "VERIFIED",
            "model_calls": 1, "verdict": "PASS"}


def test_zero_tool_false_pass_cli_exits_one(tmp_path):
    task_path, receipt_path = tmp_path / "task.json", tmp_path / "receipt.json"
    task_path.write_text(json.dumps(TASK))
    receipt_path.write_text(json.dumps(receipt()))
    result = subprocess.run([sys.executable, str(ROOT / "harness-runner.py"),
                             "--validate-execution", str(task_path), str(receipt_path)],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    assert result.stdout == ""
    assert json.loads(result.stderr) == {
        "verdict": "FAIL", "reason": "ZERO_TOOL_EXECUTION_REJECTED"}


@pytest.mark.parametrize("count", [False, "1", -1, 1.0, None])
def test_invalid_count_rejected(count):
    with pytest.raises(ExecutionRejected, match="INVALID_TOOL_EXECUTION_COUNT"):
        validate_execution(TASK, receipt(count))


def test_denied_tool_cannot_supply_execution():
    with pytest.raises(ExecutionRejected, match="ZERO_TOOL_EXECUTION_REJECTED"):
        validate_execution(TASK, receipt(0, [{"executed": False, "success": False}]))


def test_forged_count_without_dispatch_events_rejected():
    with pytest.raises(ExecutionRejected, match="COUNT_MISMATCH"):
        validate_execution(TASK, receipt(1))


def test_successful_read_cannot_satisfy_state_mutation():
    event = {"executed": True, "success": True, "state_mutation": False}
    with pytest.raises(ExecutionRejected, match="STATE_MUTATION_NOT_EXECUTED"):
        validate_execution(dict(TASK, requires_state_mutation=True), receipt(1, [event]))


def test_valid_events_still_require_task_binding_and_verified_readback():
    good = receipt(1, [{"executed": True, "success": True, "state_mutation": True}])
    assert validate_execution(TASK, good) == 1
    for field, value, reason in [("task_id", "other", "TASK_ID_MISMATCH"),
                                 ("readback_status", "claimed", "READBACK_NOT_VERIFIED")]:
        with pytest.raises(ExecutionRejected, match=reason):
            validate_execution(TASK, dict(good, **{field: value}))


@pytest.mark.parametrize("script,args", [
    ("icarus/athena-gas/test-athena.js", [str(ROOT)]),
    ("tests/grace-packet.test.cjs", []),
])
def test_apps_script_regressions(script, args):
    node = shutil.which("node") or shutil.which("nodejs")
    assert node, "Node.js required for Apps Script regressions (installed by Dockerfile)"
    result = subprocess.run([node, str(ROOT / script), *args], cwd=ROOT,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
