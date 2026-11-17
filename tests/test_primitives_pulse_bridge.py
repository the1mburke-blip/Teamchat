"""Athena ICARUS_QUEUE bridge: offline node test, plus a cross-check that the file the
pulse writes is a job the Python daemon ledger can read and claim."""
import shutil
import subprocess
from pathlib import Path

from icarus.primitives.gitledger import GitLedger

ROOT = Path(__file__).resolve().parents[1]


def test_pulse_bridge_node_and_daemon_compat(tmp_path):
    node = shutil.which("node") or shutil.which("nodejs")
    assert node, "Node.js required for Apps Script regressions (installed by Dockerfile)"
    out = tmp_path / "pulse-out"
    out.mkdir()
    r = subprocess.run([node, str(ROOT / "icarus/athena-gas/test-ledger.js"), str(ROOT), str(out)],
                       cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr

    clone = tmp_path / "clone"
    queue = clone / "icarus/ledger/queue"
    queue.mkdir(parents=True)
    shutil.copy(out / "T-001.json", queue / "T-001.json")
    job = GitLedger(clone, "main").job("T-001")
    assert job["verify_spec"] == {"expected_files": ["out.txt"]}
    assert job["task"]["source_issue"] == 7
    assert job["state"]["status"] == "queued" and job["state"]["max_attempts"] == 3
