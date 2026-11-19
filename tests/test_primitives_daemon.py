"""Git ledger + daemon executor + harness-gate adapter. Local bare repos only, no network."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from icarus.primitives.daemon import cycle
from icarus.primitives.gitledger import (BLOCKED, CLAIMED, DONE, QUEUED, ClaimLost,
                                         GitLedger, GitLedgerError, chain_ok)
from icarus.primitives.reasoner import FakeReasoner
from icarus.primitives.verify import verify

PY = sys.executable
PYNAME = Path(PY).name
HELLO = hashlib.sha256(b"hello").hexdigest()
PLAN_OK = json.dumps({"files": [{"path": "make.py",
                                 "content": "open('out.txt','w').write('hello')\n"}],
                      "commands": [[PY, "make.py"]]})
SPEC = {"expected_files": ["out.txt"], "sha256": {"out.txt": HELLO},
        "allowed_commands": [PYNAME]}


def git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True)


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


def test_enqueue_requires_spec(tmp_path, remote):
    with pytest.raises(GitLedgerError):
        clone(tmp_path, remote, "a").enqueue("j1", {"x": 1}, {}, "owner")


def test_claim_is_exclusive_across_clones(tmp_path, remote):
    a, b = clone(tmp_path, remote, "a"), clone(tmp_path, remote, "b")
    a.enqueue("j1", {"objective": "x"}, SPEC, "owner")
    assert a.claim("A")["state"]["claimed_by"] == "A"
    assert b.claim("B") is None  # b re-syncs and sees A's live lease


def test_simultaneous_claim_one_loses(tmp_path, remote):
    a, b = clone(tmp_path, remote, "a"), clone(tmp_path, remote, "b")
    a.enqueue("j1", {"objective": "x"}, SPEC, "owner")
    b.sync()
    a.claim("A")
    # simulate b deciding from stale state: make sync a no-op so b pushes on an old head
    b.sync = lambda: None
    with pytest.raises(ClaimLost):
        b.claim("B")


def test_expired_lease_reclaimable(tmp_path, remote):
    a, b = clone(tmp_path, remote, "a"), clone(tmp_path, remote, "b")
    a.enqueue("j1", {"objective": "x"}, SPEC, "owner")
    a.claim("A", lease_seconds=-1)
    assert b.claim("B")["state"]["claimed_by"] == "B"


def test_settle_only_by_holder(tmp_path, remote):
    a, b = clone(tmp_path, remote, "a"), clone(tmp_path, remote, "b")
    a.enqueue("j1", {"objective": "x"}, SPEC, "owner")
    a.claim("A")
    with pytest.raises(ClaimLost):
        b.settle("j1", "B", {"verifier": "v", "verdict": "PASS"})
    with pytest.raises(GitLedgerError):
        a.settle("j1", "A", {"verdict": "PASS"})


def test_daemon_cycle_pass_and_chain(tmp_path, remote):
    a = clone(tmp_path, remote, "a")
    a.enqueue("j1", {"objective": "write hello"}, SPEC, "owner")
    out = cycle(a, FakeReasoner([PLAN_OK]), "daemon", tmp_path / "work")
    assert out["status"] == DONE and out["receipt"]["verdict"] == "PASS"
    reader = clone(tmp_path, remote, "reader")  # fresh clone = what the pulse would see
    assert reader.job("j1")["state"]["status"] == DONE
    assert chain_ok(reader.log_path)
    assert cycle(a, FakeReasoner([]), "daemon", tmp_path / "work") == {"status": "idle"}


def test_daemon_fail_requeue_then_block(tmp_path, remote):
    a = clone(tmp_path, remote, "a")
    a.enqueue("j1", {"objective": "x"}, SPEC, "owner", max_attempts=2)
    r = FakeReasoner(["bad", "bad"])
    assert cycle(a, r, "d", tmp_path / "w")["status"] == QUEUED
    assert cycle(a, r, "d", tmp_path / "w")["status"] == BLOCKED
    assert cycle(a, r, "d", tmp_path / "w") == {"status": "idle"}


def test_outputs_never_land_in_ledger_clone(tmp_path, remote):
    a = clone(tmp_path, remote, "a")
    a.enqueue("j1", {"objective": "x"}, SPEC, "owner")
    cycle(a, FakeReasoner([PLAN_OK]), "d", tmp_path / "work")
    assert not list(a.clone.rglob("out.txt"))


# ---- harness gate adapter (runs the real icarus/harness/runner.py) ----------
def _exec():
    return {"plan_valid": True, "git_sha": None, "error": None,
            "commands": [{"argv": [PY, "make.py"], "exit_code": 0, "stdout": "", "stderr": ""}]}


def _harness(expected, pre=True):
    return {"command": [PY, "-c", "pass"], "cost_tier": "LOW", "owner_preauthorized": pre,
            "readback": {"type": "file_hash", "path": "out.txt", "expected_hash": expected}}


def test_harness_gate_pass(tmp_path):
    d = tmp_path / "job"; d.mkdir(); (d / "out.txt").write_text("hello")
    r = verify(d, {**SPEC, "harness": _harness(HELLO)}, _exec(), task_id="t1")
    assert r["verdict"] == "PASS" and r["harness"]["exit_code"] == 0


@pytest.mark.parametrize("expected,pre,code", [("0" * 64, True, 1), (HELLO, False, 3)])
def test_harness_gate_fail(tmp_path, expected, pre, code):
    d = tmp_path / "job"; d.mkdir(); (d / "out.txt").write_text("hello")
    spec = {"expected_files": ["out.txt"], "harness": _harness(expected, pre)}
    r = verify(d, spec, _exec(), task_id="t1")
    assert r["verdict"] == "FAIL" and r["harness"]["exit_code"] == code


def test_model_sees_job_limits_but_not_pass_hashes():
    from icarus.primitives.daemon import model_task
    job = {"task": {"objective": "x"}, "verify_spec": {**SPEC, "forbidden_patterns": ["GH_TOKEN"]}}
    seen = model_task(job)
    assert seen["objective"] == "x"
    assert seen["limits"]["allowed_commands"] == [PYNAME] and seen["limits"]["expected_files"] == ["out.txt"]
    assert HELLO not in json.dumps(seen) and "GH_TOKEN" not in json.dumps(seen)


def test_identity_read_from_main_while_ledger_on_other_branch(tmp_path, remote):
    from icarus.primitives.identity import load_identity
    seed = tmp_path / "seed"
    (seed / "icarus/memory").mkdir(parents=True)
    (seed / "icarus/memory/identity.md").write_text("MAIN IDENTITY")
    git(seed, "add", "-A"); git(seed, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--quiet", "-m", "id")
    git(seed, "push", "--quiet", "origin", "HEAD:main")
    git(seed, "push", "--quiet", "origin", "HEAD:icarus-ledger")
    (seed / "icarus/memory/identity.md").write_text("NEW MAIN IDENTITY")
    git(seed, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--quiet", "-am", "id2")
    git(seed, "push", "--quiet", "origin", "HEAD:main")
    c = tmp_path / "daemon"
    git(tmp_path, "clone", "--quiet", "-b", "icarus-ledger", str(remote), str(c))
    text = load_identity(c)
    assert "NEW MAIN IDENTITY" in text  # memory edits on main reach the daemon


def test_tool_call_events_are_durable_and_hash_chained(tmp_path, remote):
    a = clone(tmp_path, remote, "a")
    a.enqueue("j1", {"objective": "x"}, SPEC, "owner")
    a.record_tool_call("j1", "gha-1", {"tool_slug": "BUFFER_CREATE_POST_DRAFT",
                                          "kind": "action", "status": "started",
                                          "arguments_sha256": "abc"})
    reader = clone(tmp_path, remote, "reader")
    assert chain_ok(reader.log_path)
    events = [json.loads(line) for line in reader.log_path.read_text().splitlines()]
    assert any(e.get("type") == "tool_call" and e.get("job") == "j1"
               and e["event"].get("tool_slug") == "BUFFER_CREATE_POST_DRAFT" for e in events)
