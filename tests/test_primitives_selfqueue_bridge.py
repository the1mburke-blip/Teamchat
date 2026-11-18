"""Cross-check: a job Icarus self-queues in the pulse (cloud-4.6) is a valid ledger job for the daemon."""
import shutil
import subprocess
from pathlib import Path

from icarus.primitives.gitledger import GitLedger

ROOT = Path(__file__).resolve().parents[1]


def test_self_queued_job_loads_in_daemon_ledger(tmp_path):
    node = shutil.which("node") or shutil.which("nodejs")
    assert node, "Node.js required for Apps Script regressions (installed by Dockerfile)"
    out = tmp_path / "pulse-out"
    out.mkdir()
    r = subprocess.run([node, str(ROOT / "icarus/athena-gas/test-selfqueue.js"), str(ROOT), str(out)],
                       cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr

    clone = tmp_path / "clone"
    queue = clone / "icarus/ledger/queue"
    queue.mkdir(parents=True)
    shutil.copy(out / "auto-job.json", queue / "auto-202611181000-50.json")
    job = GitLedger(clone, "main").job("auto-202611181000-50")
    assert job["verify_spec"]["expected_files"] == ["checklist.md"]
    assert "GH_TOKEN" in job["verify_spec"]["forbidden_patterns"]
    assert job["task"]["source_issue"] == 50
    assert job["state"]["status"] == "queued"
