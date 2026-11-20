"""Receipts must show what ran, and require_command_output must catch model-typed answers."""
import sys
from pathlib import Path

from icarus.primitives.runner import execute
from icarus.primitives.verify import verify

PY = Path(sys.executable).name
SPEC = {"expected_files": ["out.txt"], "allowed_commands": [PY], "require_command_output": True}


def run(tmp_path, plan, spec=SPEC):
    job = {"verify_spec": spec}
    rec = execute(job, plan, tmp_path)
    return rec, verify(tmp_path, spec, rec, task_id="t")


def test_model_typed_answer_fails(tmp_path):
    plan = {"files": [{"path": "out.txt", "content": "BLOCKED"}], "commands": []}
    rec, r = run(tmp_path, plan)
    assert r["verdict"] == "FAIL"
    assert any("no command ran" in x for x in r["gate_1_technical"]["reasons"])
    assert any("written by the model's plan" in x for x in r["gate_1_technical"]["reasons"])
    assert r["plan_files"] == ["out.txt"] and r["commands"] == []


def test_typed_answer_plus_dummy_command_still_fails(tmp_path):
    plan = {"files": [{"path": "out.txt", "content": "BLOCKED"}],
            "commands": [[sys.executable, "-c", "pass"]]}
    _, r = run(tmp_path, plan)
    assert r["verdict"] == "FAIL"
    assert any("written by the model's plan" in x for x in r["gate_1_technical"]["reasons"])


def test_command_produced_output_passes_and_is_recorded(tmp_path):
    plan = {"files": [{"path": "make.py", "content": "open('out.txt','w').write('measured')\n"}],
            "commands": [[sys.executable, "make.py"]]}
    _, r = run(tmp_path, plan)
    assert r["verdict"] == "PASS", r
    assert r["commands"][0]["argv0"] == PY and r["commands"][0]["exit_code"] == 0
    assert len(r["commands"][0]["stdout_sha256"]) == 64 and "stdout" not in r["commands"][0]
    assert r["plan_files"] == ["make.py"]


def test_command_overwriting_a_plan_file_counts_as_command_output(tmp_path):
    plan = {"files": [{"path": "out.txt", "content": "placeholder"},
                      {"path": "make.py", "content": "open('out.txt','w').write('measured')\n"}],
            "commands": [[sys.executable, "make.py"]]}
    _, r = run(tmp_path, plan)
    assert r["verdict"] == "PASS", r


def test_rule_off_keeps_old_behaviour(tmp_path):
    spec = {"expected_files": ["out.txt"], "allowed_commands": [PY]}
    _, r = run(tmp_path, {"files": [{"path": "out.txt", "content": "x"}], "commands": []}, spec)
    assert r["verdict"] == "PASS" and r["plan_files"] == ["out.txt"]
