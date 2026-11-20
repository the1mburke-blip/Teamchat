"""Daemon liveness heartbeat on the git ledger. Local bare repos only, no network."""
import json
import subprocess

import pytest

from icarus.primitives.daemon import Heartbeat
from icarus.primitives.gitledger import GitLedger, GitLedgerError, chain_ok


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def remote(tmp_path):
    bare = tmp_path / "remote.git"
    git(tmp_path, "init", "--quiet", "--bare", "-b", "main", str(bare))
    seed = tmp_path / "seed"
    git(tmp_path, "clone", "--quiet", str(bare), str(seed))
    (seed / "README").write_text("x")
    git(seed, "add", "README")
    git(seed, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--quiet", "-m", "init")
    git(seed, "push", "--quiet", "origin", "HEAD:main")
    return bare


def clone(tmp_path, remote, name):
    d = tmp_path / name
    git(tmp_path, "clone", "--quiet", str(remote), str(d))
    return GitLedger(d, "main")


class Clock:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def read_remote_heartbeat(tmp_path, remote, runner="laptop-daemon"):
    reader = clone(tmp_path, remote, f"reader-{len(list(tmp_path.iterdir()))}")
    p = reader.base / "heartbeat" / f"{runner}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def test_heartbeat_is_pushed_and_readable_from_a_fresh_clone(tmp_path, remote, monkeypatch):
    monkeypatch.setenv("ICARUS_BUILD_SHA", "abc1234")
    a = clone(tmp_path, remote, "a")
    hb = Heartbeat(a, "laptop-daemon", 1800, clock=Clock())
    hb.note({"status": "idle"})
    assert hb.beat() is True
    beat = read_remote_heartbeat(tmp_path, remote)
    assert beat["runner"] == "laptop-daemon"
    assert beat["utc"] == "2027-01-15T08:00:00Z"
    assert beat["last_status"] == "idle" and beat["build"] == "abc1234"
    assert "liveness only" in beat["note"]


def test_heartbeat_never_touches_job_evidence(tmp_path, remote):
    a = clone(tmp_path, remote, "a")
    Heartbeat(a, "laptop-daemon", 1800, clock=Clock()).beat()
    reader = clone(tmp_path, remote, "reader")
    assert not reader.log_path.exists(), "heartbeat must not be chained into run_log.jsonl"
    assert not (reader.base / "state").exists() and not (reader.base / "queue").exists()
    assert chain_ok(reader.log_path)


def test_heartbeat_interval_gates_pushes(tmp_path, remote):
    a = clone(tmp_path, remote, "a")
    clock = Clock()
    hb = Heartbeat(a, "laptop-daemon", 1800, clock=clock)
    assert hb.beat() is True          # first pass always beats (a restart is visible at once)
    clock.t += 1799
    assert hb.beat() is None          # not due yet: no commit
    clock.t += 1
    assert hb.beat() is True
    log = git(tmp_path / "a", "log", "--format=%s").stdout.split("\n")
    assert sum(1 for s in log if s == "ledger: heartbeat laptop-daemon") == 2


def test_interval_zero_disables(tmp_path, remote):
    a = clone(tmp_path, remote, "a")
    assert Heartbeat(a, "laptop-daemon", 0, clock=Clock()).beat() is None
    assert read_remote_heartbeat(tmp_path, remote) is None


def test_counts_settled_jobs_not_claim_losses(tmp_path, remote):
    hb = Heartbeat(clone(tmp_path, remote, "a"), "laptop-daemon", 1800, clock=Clock())
    hb.note({"status": "done", "job": "j1", "receipt": {"verdict": "PASS"}})
    hb.note({"status": "claim_lost", "job": "j2", "receipt": {"verdict": "PASS"}})
    hb.note({"status": "idle"})
    assert hb.settled == 1 and hb.last_status == "idle"


def test_push_failure_returns_false_and_retries_next_pass(tmp_path, remote):
    a = clone(tmp_path, remote, "a")
    clock = Clock()
    hb = Heartbeat(a, "laptop-daemon", 1800, clock=clock)
    calls = []

    def failing(runner_id, payload):
        calls.append(payload)
        raise GitLedgerError("push rejected")

    a.heartbeat = failing
    assert hb.beat() is False         # never raises into the daemon loop
    assert hb.beat() is False         # still due: retried on the next pass, not 30 min later
    assert len(calls) == 2


def test_rejected_push_resyncs_without_raising(tmp_path, remote):
    a, b = clone(tmp_path, remote, "a"), clone(tmp_path, remote, "b")
    assert a.heartbeat("laptop-daemon", {"utc": "t1"}) is True
    # b is behind the remote: its push is rejected, it reports False and re-syncs to the remote
    b._git("reset", "--quiet", "--hard", "HEAD")
    assert b.heartbeat.__self__ is b
    (b.clone / "x").write_text("y")  # untracked noise must not break the beacon
    assert b.heartbeat("laptop-daemon", {"utc": "t2"}) in (True, False)
    assert read_remote_heartbeat(tmp_path, remote)["utc"] in ("t1", "t2")


@pytest.mark.parametrize("bad", ["", "../x", "a/b", ".hidden", "a\\b"])
def test_bad_runner_ids_refused(tmp_path, remote, bad):
    with pytest.raises(GitLedgerError):
        clone(tmp_path, remote, "a").heartbeat(bad, {"utc": "t"})
