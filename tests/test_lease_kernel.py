import concurrent.futures
import json
import subprocess
import time
from unittest.mock import patch

import pytest

from dsh.cordis.kernel import (
    CordisKernel, FileLeaseStore, GitLeaseStore, LeaseBusyError, LeaseError, LeaseLock,
)


def test_stale_lease_acquisition_cloud_takes_over_when_laptop_stops_heartbeating(tmp_path):
    now = [1000.0]
    laptop = LeaseLock(tmp_path, owner="laptop", ttl=30, clock=lambda: now[0])
    cloud = LeaseLock(tmp_path, owner="cloud", ttl=30, clock=lambda: now[0])
    assert laptop.acquire()
    now[0] += 31
    assert cloud.acquire()
    record = json.loads((tmp_path / ".icarus_lease.lock").read_text())
    assert record["owner"] == "cloud"
    assert record["token"] == cloud.token
    with pytest.raises(LeaseError):
        laptop.heartbeat()
    assert not laptop.release()
    cloud.assert_owned()


def test_active_lease_yielding_cloud_steps_back_while_laptop_holds_lease(tmp_path):
    now = [1000.0]
    laptop = LeaseLock(tmp_path, owner="laptop", ttl=30, clock=lambda: now[0])
    cloud = LeaseLock(tmp_path, owner="cloud", ttl=30, clock=lambda: now[0])
    assert laptop.acquire()
    before = (tmp_path / ".icarus_lease.lock").read_bytes()
    assert not cloud.acquire()
    assert (tmp_path / ".icarus_lease.lock").read_bytes() == before
    laptop.assert_owned()


def test_heartbeat_extends_lease_and_expiry_boundary_allows_takeover(tmp_path):
    now = [1000.0]
    laptop = LeaseLock(tmp_path, ttl=30, clock=lambda: now[0])
    cloud = LeaseLock(tmp_path, owner="cloud", ttl=30, clock=lambda: now[0])
    assert laptop.acquire()
    now[0] += 20
    laptop.heartbeat()
    now[0] += 10
    assert not cloud.acquire()
    now[0] += 20
    assert cloud.acquire()


def test_simultaneous_file_acquisition_has_one_winner(tmp_path):
    leases = [LeaseLock(tmp_path) for _ in range(8)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(lambda lease: lease.acquire(), leases)) == 1


def test_corrupt_lease_is_not_assumed_stale(tmp_path):
    (tmp_path / ".icarus_lease.lock").write_text("broken lease", encoding="utf-8")
    with pytest.raises(LeaseError, match="Invalid lease"):
        LeaseLock(tmp_path).acquire()


def test_kernel_cannot_write_while_another_local_worker_holds_lease(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text("value = 1\n", encoding="utf-8")
    laptop = LeaseLock(tmp_path)
    assert laptop.acquire()
    with pytest.raises(LeaseBusyError), patch("dsh.cordis.kernel.subprocess.run") as run:
        CordisKernel(tmp_path).apply_and_verify("sample.py", "value = 2\n")
    run.assert_not_called()
    assert target.read_text() == "value = 1\n"


def test_heartbeat_thread_runs_and_release_occurs_on_exception(tmp_path):
    lease = LeaseLock(tmp_path, ttl=0.3)
    with pytest.raises(RuntimeError, match="worker failed"):
        with lease.hold():
            initial = FileLeaseStore(tmp_path).read().record["heartbeat_at"]
            deadline = time.monotonic() + 3
            while FileLeaseStore(tmp_path).read().record["heartbeat_at"] == initial:
                assert time.monotonic() < deadline
                time.sleep(0.02)
            raise RuntimeError("worker failed")
    assert FileLeaseStore(tmp_path).read().record["owner"] == "released"


def git(root, *args):
    return subprocess.run(
        ["git", "-c", "user.name=Lease Test", "-c", "user.email=lease@example.invalid", *args],
        cwd=root, capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout.strip()


@pytest.fixture
def lease_repositories(tmp_path):
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "--bare", str(origin))
    laptop, cloud = tmp_path / "laptop", tmp_path / "cloud"
    git(tmp_path, "clone", str(origin), str(laptop))
    git(laptop, "checkout", "-b", "main")
    (laptop / ".gitignore").write_text(".icarus_lease.lock\n__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    (laptop / "sample.py").write_text("value = 1\n", encoding="utf-8")
    (laptop / "test_contract.py").write_text(
        "import pathlib\nimport runpy\n"
        "def test_generated_values():\n"
        "    root = pathlib.Path(__file__).parent\n"
        "    assert runpy.run_path(str(root / 'sample.py'))['value'] == 2\n"
        "    if (root / 'other.py').is_file():\n"
        "        assert runpy.run_path(str(root / 'other.py'))['value'] == 3\n", encoding="utf-8",
    )
    (laptop / "GOAL.md").write_text(
        "# Test goal\n<!-- icarus:tasks -->\n"
        "- [ ] `sample.py` :: Set value to two\n"
        "- [ ] `other.py` :: Set value to three\n"
        "<!-- /icarus:tasks -->\n", encoding="utf-8",
    )
    git(laptop, "add", ".")
    git(laptop, "commit", "-m", "initial")
    git(laptop, "push", "-u", "origin", "main")
    git(tmp_path, "clone", "--branch", "main", str(origin), str(cloud))
    return origin, laptop, cloud


def test_shared_git_lease_coordinates_separate_laptop_and_cloud_clones(lease_repositories):
    _, laptop_root, cloud_root = lease_repositories
    now = [1000.0]
    laptop = LeaseLock(laptop_root, store=GitLeaseStore(laptop_root), ttl=30, clock=lambda: now[0])
    cloud = LeaseLock(cloud_root, owner="cloud", store=GitLeaseStore(cloud_root), ttl=30, clock=lambda: now[0])
    assert laptop.acquire()
    assert not cloud.acquire()
    now[0] += 31
    assert cloud.acquire()
    with pytest.raises(LeaseError):
        laptop.store.publish_main(laptop)
    assert not laptop.release()
    cloud.assert_owned()
    assert (laptop_root / ".icarus_lease.lock").exists()
    assert (cloud_root / ".icarus_lease.lock").exists()


def test_shared_git_cas_rejects_a_racing_takeover(lease_repositories):
    _, laptop_root, cloud_root = lease_repositories
    laptop, cloud = GitLeaseStore(laptop_root), GitLeaseStore(cloud_root)
    stale_revision = cloud.read().revision
    assert laptop.compare_and_swap(None, LeaseLock().record())
    assert not cloud.compare_and_swap(stale_revision, LeaseLock(owner="cloud").record())


def test_atomic_publication_rejects_lease_change_after_ownership_check(lease_repositories):
    origin, laptop_root, cloud_root = lease_repositories
    store = GitLeaseStore(laptop_root)
    now = [1000.0]
    laptop = LeaseLock(laptop_root, store=store, ttl=30, clock=lambda: now[0])
    assert laptop.acquire()
    old_main = git(origin, "rev-parse", "refs/heads/main")
    (laptop_root / "sample.py").write_text("value = 2\n", encoding="utf-8")
    git(laptop_root, "add", "sample.py")
    git(laptop_root, "commit", "-m", "candidate")
    commit_record = store._commit_record

    def takeover_then_commit(record, parent):
        # Competing owner advances the authority after the publisher checked it.
        now[0] += 31
        cloud = LeaseLock(cloud_root, owner="cloud", ttl=30, store=GitLeaseStore(cloud_root),
                          clock=lambda: now[0])
        assert cloud.acquire()
        return commit_record(record, parent)

    with patch.object(store, "_commit_record", side_effect=takeover_then_commit) as prepare:
        with pytest.raises(LeaseError):
            store.publish_main(laptop)
    prepare.assert_called_once()
    assert git(origin, "rev-parse", "refs/heads/main") == old_main


def test_kernel_rolls_back_if_lease_is_taken_over_during_tests(tmp_path):
    now = [1000.0]
    laptop = LeaseLock(tmp_path, ttl=30, clock=lambda: now[0])
    cloud = LeaseLock(tmp_path, owner="cloud", ttl=30, clock=lambda: now[0])
    assert laptop.acquire()
    target = tmp_path / "sample.py"
    target.write_bytes(b"value = 1\r\n")

    def tests_finish_after_takeover(*args, **kwargs):
        now[0] += 31
        assert cloud.acquire()
        return subprocess.CompletedProcess(["pytest"], 0, "", "")

    with patch("dsh.cordis.kernel.notify_human"), patch(
        "dsh.cordis.kernel.subprocess.run", side_effect=tests_finish_after_takeover
    ), pytest.raises(SystemExit) as result:
        CordisKernel(tmp_path, lease=laptop).apply_and_verify("sample.py", "value = 2\n")
    assert result.value.code == 1
    assert target.read_bytes() == b"value = 1\r\n"
    cloud.assert_owned()
