"""Job commands must not inherit the daemon's credentials (synthetic values only, no network)."""
import json
import sys
from pathlib import Path

from icarus.primitives.jobenv import job_env
from icarus.primitives.runner import execute
from icarus.primitives.verify import harness_gate

SECRETS = {"GH_TOKEN": "ghp_SYNTHETIC0000000000000000000000000",
           "GEMINI_API_KEY": "AIzaSYNTHETIC00000000000000000000000",
           "OPENROUTER_API_KEY": "sk-or-SYNTHETIC0000",
           "GITHUB_PAT": "github_pat_SYNTHETIC", "ANY_OTHER_TOKEN": "tok_SYNTHETIC_OTHER_7731"}

DUMP = "import json, os; open('env.json','w').write(json.dumps(dict(os.environ)))\n"


def run_dump(tmp_path, monkeypatch):
    for k, v in SECRETS.items():
        monkeypatch.setenv(k, v)
    job = {"verify_spec": {"allowed_commands": [Path(sys.executable).name]}}
    plan = {"files": [{"path": "dump.py", "content": DUMP}],
            "commands": [[sys.executable, "dump.py"]]}
    rec = execute(job, plan, tmp_path)
    assert rec["error"] is None and rec["commands"][0]["exit_code"] == 0, rec
    return json.loads((tmp_path / "env.json").read_text())


def test_job_cannot_see_daemon_credentials(tmp_path, monkeypatch):
    env = run_dump(tmp_path, monkeypatch)
    for k, v in SECRETS.items():
        assert k not in env, k
        assert v not in json.dumps(env), k


def test_job_home_and_temp_are_the_job_dir(tmp_path, monkeypatch):
    env = run_dump(tmp_path, monkeypatch)
    d = str(tmp_path.resolve())
    for k in ("HOME", "TMPDIR", "TEMP", "TMP"):
        assert env[k] == d, k


def test_harness_command_cannot_see_daemon_credentials(tmp_path, monkeypatch):
    """Second leak path: verify.harness_gate -> icarus.harness.runner -> author's command."""
    for k, v in SECRETS.items():
        monkeypatch.setenv(k, v)
    job_dir = tmp_path / "attempt-1"
    job_dir.mkdir()
    (job_dir / "dump.py").write_text(DUMP)
    harness_gate(job_dir, "env-test", {"command": [sys.executable, "dump.py"], "owner_preauthorized": True,
                                       "readback": {"type": "file_hash", "path": "env.json",
                                                    "expected_hash": "0" * 64}})
    assert (job_dir / "env.json").exists(), "harness did not run the command"
    dumped = (job_dir / "env.json").read_text()
    for k, v in SECRETS.items():
        assert k not in json.loads(dumped) and v not in dumped, k


def test_job_env_is_an_allowlist(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMETHING_NEW_SECRET", "s")
    env = job_env(tmp_path)
    assert "SOMETHING_NEW_SECRET" not in env
    allowed = {"PATH", "LANG", "LC_ALL", "TZ", "SYSTEMROOT", "WINDIR",
               "HOME", "USERPROFILE", "TMPDIR", "TEMP", "TMP", "PYTHONNOUSERSITE"}
    assert set(env) <= allowed
