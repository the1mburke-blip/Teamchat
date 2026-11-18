"""Cloud worker hardening (ICARUS-CLOUDIFY-20261118): no credential inheritance,
no-network sandbox, cloud host skips laptop-only jobs, drain mode. Local bare repos only."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from icarus.primitives import daemon as d
from icarus.primitives.gitledger import DONE, GitLedger
from icarus.primitives.reasoner import FakeReasoner
from icarus.primitives.runner import _sandboxed, execute

sys.path.insert(0, str(Path(__file__).parent))
from test_primitives_daemon import SPEC, PLAN_OK, clone, remote  # noqa: E402,F401

LEAK = "ghp_" + "Z" * 36


def _job(cmds):
    return {"verify_spec": {"expected_files": ["env.txt"], "allowed_commands": ["sh"]}}, \
        {"files": [], "commands": cmds}


def test_child_does_not_inherit_daemon_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", LEAK)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza" + "x" * 35)
    monkeypatch.delenv("ICARUS_SANDBOX", raising=False)
    job, plan = _job([["sh", "-c", "env > env.txt"]])
    rec = execute(job, plan, tmp_path)
    assert rec["commands"][0]["exit_code"] == 0
    env = (tmp_path / "env.txt").read_text()
    assert LEAK not in env and "GEMINI_API_KEY" not in env and "GH_TOKEN" not in env
    assert f"HOME={tmp_path}" in env


def test_sandbox_argv_has_no_network_and_only_job_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_SANDBOX", "docker")
    argv, cwd = _sandboxed(["sh", "-c", "echo hi"], tmp_path)
    assert cwd is None and argv[:3] == ["docker", "run", "--rm"]
    s = " ".join(argv)
    assert "--network none" in s and "--read-only" in s and "--cap-drop ALL" in s
    assert f"{tmp_path.resolve()}:/job:rw" in s and "/var/run/docker.sock" not in s
    assert not any(a.startswith(("GH_TOKEN", "GEMINI")) for a in argv)
    assert argv[-3:] == ["sh", "-c", "echo hi"]


IMAGE = os.environ.get("ICARUS_SANDBOX_IMAGE", "python:3.12-slim")


def _docker_ok():
    if not shutil.which("docker"):
        return False
    r = subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True)
    return r.returncode == 0


@pytest.mark.skipif(not _docker_ok(), reason="docker + sandbox image not available")
def test_real_sandbox_blocks_network_and_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_SANDBOX", "docker")
    monkeypatch.setenv("GH_TOKEN", LEAK)
    job, plan = _job([["sh", "-c", "env > env.txt; python3 -c \"import socket;"
                       "socket.create_connection(('1.1.1.1',443),3)\" && echo NET-OPEN >> env.txt"
                       " || echo NET-BLOCKED >> env.txt; true"]])
    rec = execute(job, plan, tmp_path)
    out = (tmp_path / "env.txt").read_text()
    assert rec["commands"][0]["exit_code"] == 0, rec
    assert LEAK not in out and "NET-BLOCKED" in out and "NET-OPEN" not in out


def test_cloud_host_skips_laptop_only_jobs(tmp_path, remote):
    a = clone(tmp_path, remote, "a")
    a.enqueue("j-laptop", {"o": 1}, SPEC, author="owner")
    q = a.base / "queue" / "j-laptop.json"
    data = json.loads(q.read_text()); data["execution_target"] = "laptop-only"
    q.write_text(json.dumps(data))
    a._commit_push([q], "mark laptop-only")
    a.enqueue("j-any", {"o": 2}, SPEC, author="owner")
    c = clone(tmp_path, remote, "c")
    got = c.claim("gha-1-1", 1800, host="cloud")
    assert got["id"] == "j-any"
    assert c.claim("gha-1-1", 1800, host="cloud") is None
    assert clone(tmp_path, remote, "l").claim("laptop-daemon", 600)["id"] == "j-laptop"


def test_drain_runs_until_idle(tmp_path, remote, monkeypatch):
    a = clone(tmp_path, remote, "a")
    for j in ("j1", "j2"):
        a.enqueue(j, {"o": j}, SPEC, author="owner")
    w = clone(tmp_path, remote, "w")
    monkeypatch.setenv("ICARUS_LEDGER_CLONE", str(w.clone))
    monkeypatch.setenv("ICARUS_LEDGER_BRANCH", "main")
    monkeypatch.setenv("ICARUS_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("ICARUS_RUNNER_ID", "gha-9-1")
    monkeypatch.setenv("ICARUS_HOST", "cloud")
    monkeypatch.delenv("ICARUS_SANDBOX", raising=False)
    monkeypatch.setattr(d, "load_pool", lambda *a, **k: [{"model": "fake"}])
    monkeypatch.setattr(d, "ModelSwitcher", lambda *a, **k: FakeReasoner([PLAN_OK, PLAN_OK]))
    assert d.main(["--drain", "5"]) == 0
    check = clone(tmp_path, remote, "check")
    assert [check.job(j)["state"]["status"] for j in ("j1", "j2")] == [DONE, DONE]
    log = [json.loads(l) for l in check.log_path.read_text().splitlines() if l.strip()]
    assert {(r["job"], r["runner"]) for r in log if r["type"] == "receipt"} == \
        {("j1", "gha-9-1"), ("j2", "gha-9-1")}


def test_harness_gate_gets_no_daemon_secrets(tmp_path, monkeypatch):
    from icarus.primitives.verify import harness_gate
    monkeypatch.setenv("GH_TOKEN", LEAK)
    jd = tmp_path / "attempt-1"; jd.mkdir()
    (jd / "check.py").write_text("import os\nopen('seen.txt','w').write(os.environ.get('GH_TOKEN','none'))\n")
    harness_gate(jd, "t", {"command": [sys.executable, "check.py"], "owner_preauthorized": True,
                           "readback": {"type": "file_hash", "path": "seen.txt",
                                        "expected_hash": "0" * 64}})
    assert (jd / "seen.txt").read_text() == "none"
