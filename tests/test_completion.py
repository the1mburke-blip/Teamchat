import os
import pathlib
import sys
from unittest.mock import patch

import pytest

from dsh.completion import parse_goal, run_completion_loop
from dsh.cordis.kernel import GitLeaseStore, LeaseLock, VerificationError
from dsh.runner import run_harness_task
from test_lease_kernel import git, lease_repositories


@pytest.fixture(autouse=True)
def local_test_environment(monkeypatch):
    monkeypatch.setenv("PATH", str(pathlib.Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""))
    with patch("dsh.cordis.kernel.notify_human"):
        yield


def test_completion_loop_runs_real_kernel_and_pytest_publishes_each_task_then_stops(lease_repositories):
    origin, laptop, cloud = lease_repositories
    initial = git(origin, "rev-parse", "refs/heads/main")
    with patch("dsh.runner.call_llm_raw", side_effect=["value = 2\n", "value = 3\n"]) as model, patch(
        "dsh.cordis.kernel.notify_human"
    ) as notification:
        assert run_completion_loop(cloud, owner="cloud", execute=run_harness_task) == 0
    assert model.call_count == 2
    notification.assert_not_called()
    remote_goal = git(origin, "show", "refs/heads/main:GOAL.md")
    assert "[ ]" not in remote_goal
    assert remote_goal.count("[x]") == 2
    assert git(origin, "show", "refs/heads/main:other.py") == "value = 3"
    assert git(origin, "rev-list", "--count", f"{initial}..refs/heads/main") == "2"
    assert git(cloud, "status", "--porcelain") == ""
    assert GitLeaseStore(laptop).read().record["owner"] == "released"


def test_cloud_yields_to_live_laptop_without_any_model_call_or_main_commit(lease_repositories):
    origin, laptop, cloud = lease_repositories
    lease = LeaseLock(laptop, store=GitLeaseStore(laptop))
    assert lease.acquire()
    initial = git(origin, "rev-parse", "refs/heads/main")
    with patch("dsh.runner.call_llm_raw") as model:
        assert run_completion_loop(cloud, owner="cloud", execute=run_harness_task) == 0
    model.assert_not_called()
    assert git(origin, "rev-parse", "refs/heads/main") == initial
    lease.assert_owned()


def test_real_test_failure_restores_target_and_does_not_complete_or_publish(lease_repositories):
    origin, _, cloud = lease_repositories
    initial = git(origin, "rev-parse", "refs/heads/main")
    before = (cloud / "GOAL.md").read_bytes()
    original = (cloud / "sample.py").read_bytes()
    with patch("dsh.runner.call_llm_raw", return_value="value = 99\n"):
        with pytest.raises(SystemExit) as result:
            run_completion_loop(cloud, owner="cloud", execute=run_harness_task)
    assert result.value.code == 1
    assert (cloud / "sample.py").read_bytes() == original
    assert (cloud / "GOAL.md").read_bytes() == before
    assert git(origin, "rev-parse", "refs/heads/main") == initial
    assert GitLeaseStore(cloud).read().record["owner"] == "released"


def test_bounded_loop_persists_progress_then_resumes_remaining_work(lease_repositories):
    origin, _, cloud = lease_repositories
    with patch("dsh.runner.call_llm_raw", return_value="value = 2\n") as first:
        assert run_completion_loop(cloud, owner="cloud", max_tasks=1, execute=run_harness_task) == 2
    first.assert_called_once()
    assert git(origin, "show", "refs/heads/main:GOAL.md").count("[ ]") == 1
    with patch("dsh.runner.call_llm_raw", return_value="value = 3\n") as second:
        assert run_completion_loop(cloud, owner="cloud", execute=run_harness_task) == 0
    second.assert_called_once()
    assert "[ ]" not in git(origin, "show", "refs/heads/main:GOAL.md")


def test_worker_cannot_mark_its_own_goal_complete(lease_repositories):
    origin, _, cloud = lease_repositories
    initial = git(origin, "rev-parse", "refs/heads/main")

    def malicious_worker(*args, **kwargs):
        goal = cloud / "GOAL.md"
        goal.write_text(goal.read_text().replace("[ ]", "[x]"), encoding="utf-8")

    with pytest.raises(VerificationError, match="modified GOAL"):
        run_completion_loop(cloud, owner="cloud", execute=malicious_worker)
    assert git(origin, "rev-parse", "refs/heads/main") == initial


def test_unrelated_files_are_not_staged_or_published(lease_repositories):
    origin, _, cloud = lease_repositories
    initial = git(origin, "rev-parse", "refs/heads/main")

    def extra_file(*args, **kwargs):
        (cloud / "unrelated.txt").write_text("unexpected", encoding="utf-8")

    with pytest.raises(VerificationError, match="outside its declared target"):
        run_completion_loop(cloud, owner="cloud", execute=extra_file)
    assert git(cloud, "diff", "--cached", "--name-only") == ""
    assert git(origin, "rev-parse", "refs/heads/main") == initial


@pytest.mark.parametrize("body", [
    "ordinary unchecked prose",
    "<!-- icarus:tasks -->\n- [ ] fix everything\n<!-- /icarus:tasks -->",
    "<!-- icarus:tasks -->\n- [ ] `../outside.py` :: escape\n<!-- /icarus:tasks -->",
    "<!-- icarus:tasks -->\n- [ ] `GOAL.md` :: mark complete\n<!-- /icarus:tasks -->",
    "<!-- icarus:tasks -->\n<!-- /icarus:tasks -->",
])
def test_goal_format_fails_closed(body):
    with pytest.raises(VerificationError):
        parse_goal(body)


def test_goal_parser_ignores_historical_checklists_outside_managed_block():
    tasks = parse_goal(
        "- [ ] unresolved host audit\n<!-- icarus:tasks -->\n"
        "- [x] `sample.py` :: Implement value\n<!-- /icarus:tasks -->\n"
    )
    assert len(tasks) == 1 and tasks[0].done
