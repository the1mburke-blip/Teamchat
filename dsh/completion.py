"""Leased laptop/cloud task execution with deterministic goal bookkeeping."""

import argparse
import contextlib
import pathlib
import re
import sys
from dataclasses import dataclass

from dsh.cordis.kernel import (
    CordisKernel, GitLeaseStore, LeaseBusyError, LeaseError, LeaseLock, VerificationError,
)
from dsh.runner import run_harness_task


@dataclass(frozen=True)
class GoalTask:
    line: int
    done: bool
    target: str
    instruction: str


def parse_goal(text):
    start, end = "<!-- icarus:tasks -->", "<!-- /icarus:tasks -->"
    lines = text.splitlines(keepends=True)
    if text.count(start) != 1 or text.count(end) != 1:
        raise VerificationError("GOAL.md requires exactly one managed task block")
    first = next((i for i, line in enumerate(lines) if line.strip() == start), -1)
    last = next((i for i, line in enumerate(lines) if line.strip() == end), -1)
    if first < 0 or last <= first:
        raise VerificationError("Invalid GOAL.md task block boundaries")
    tasks = []
    for index in range(first + 1, last):
        line = lines[index].strip()
        if not line:
            continue
        match = re.fullmatch(r"- \[([ xX])\] `([^`]+)` :: (\S.*)", line)
        if not match:
            raise VerificationError(f"Invalid managed task at GOAL.md line {index + 1}")
        done, target, instruction = match.groups()
        if (pathlib.PurePosixPath(target).is_absolute() or "\\" in target
                or ":" in target or ".." in target.split("/")
                or target.casefold() in {"goal.md", ".icarus_lease.lock"}):
            raise VerificationError("Goal tasks require a relative, non-control target")
        tasks.append(GoalTask(index, done.lower() == "x", target, instruction))
    if not tasks:
        raise VerificationError("GOAL.md managed block is empty")
    return tasks


def _clean(store):
    if store.git("status", "--porcelain").stdout.strip():
        raise VerificationError("Completion loop requires a clean working tree")


def _sync(store):
    _clean(store)
    if store.git("branch", "--show-current").stdout.strip() != "main":
        raise VerificationError("Completion loop runs on main only")
    store.git("pull", "--ff-only", "origin", "main")
    remote = store.git("ls-remote", "--exit-code", "origin", "refs/heads/main").stdout.split()[0]
    if store.git("rev-parse", "HEAD").stdout.strip() != remote:
        raise VerificationError("Local main has unpublished commits; recover before resuming")


def _check_changes(store, allowed):
    # Inspect tracked and untracked paths, with NUL separators for unusual names.
    changed = store.git("diff", "--name-only", "-z", "HEAD").stdout.split("\0")
    changed += store.git("ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0")
    if set(filter(None, changed)) - set(allowed):
        raise VerificationError("Task changed files outside its declared target")


def _publish(store, lease, paths, message):
    lease.assert_owned()
    store.git("add", "--", *paths)
    if not store.git("diff", "--cached", "--name-only").stdout.strip():
        print("[ICARUS] Task verified; no file changes to publish.")
        return
    store.git("commit", "-m", message)
    store.publish_main(lease)


def run_completion_loop(root=".", *, owner="laptop", max_tasks=20, ttl=300,
                        execute=run_harness_task, mode="goals", target=None, instruction=None):
    """Return 0 for managed completion/yield, 2 for pending tasks at the limit.

    Provider/test/publication errors propagate and do not mark remote work done.
    Real provider calls are made only by execute; tests supply a deterministic worker.
    """
    if max_tasks < 1 or max_tasks > 100:
        raise ValueError("max_tasks must be between 1 and 100")
    if mode not in {"goals", "task"} or mode == "task" and (not target or not instruction):
        raise ValueError("Task mode requires target and instruction")
    root = pathlib.Path(root).resolve()
    store = GitLeaseStore(root)
    lease = LeaseLock(root, owner=owner, ttl=ttl, store=store)
    try:
        with lease.hold(), contextlib.chdir(root):
            _sync(store)
            if mode == "task":
                CordisKernel(root, notify=False).validate_path(target)
                execute(target, instruction, lease=lease, sync=False)
                _check_changes(store, [target])
                _publish(store, lease, [target], "chore(icarus): verified kernel update")
                return 0
            goal = root / "GOAL.md"
            for _ in range(max_tasks):
                before = goal.read_bytes()
                text = before.decode("utf-8")
                pending = [task for task in parse_goal(text) if not task.done]
                if not pending:
                    print("[ICARUS] All managed GOAL.md tasks complete.")
                    return 0
                task = pending[0]
                CordisKernel(root, notify=False).validate_path(task.target)
                lease.assert_owned()
                execute(task.target, task.instruction, lease=lease, sync=False)
                lease.assert_owned()
                if goal.read_bytes() != before:
                    raise VerificationError("Worker modified GOAL.md; refusing completion")
                _check_changes(store, [task.target])
                lines = text.splitlines(keepends=True)
                lines[task.line] = lines[task.line].replace("[ ]", "[x]", 1)
                goal.write_bytes("".join(lines).encode("utf-8"))
                _publish(store, lease, [task.target, "GOAL.md"], f"chore(icarus): complete {task.target}")
            if any(not task.done for task in parse_goal(goal.read_text(encoding="utf-8"))):
                print("[ICARUS] Task limit reached; managed work remains.")
                return 2
            print("[ICARUS] All managed GOAL.md tasks complete.")
            return 0
    except LeaseBusyError:
        print("[ICARUS YIELD] Another worker has an active lease; no task executed.")
        return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", choices=("laptop", "cloud"), default="laptop")
    parser.add_argument("--mode", choices=("goals", "task"), default="goals")
    parser.add_argument("--max-tasks", type=int, default=20)
    parser.add_argument("--ttl", type=float, default=300)
    parser.add_argument("--target-file")
    parser.add_argument("--instruction")
    args = parser.parse_args(argv)
    try:
        return run_completion_loop(owner=args.owner, mode=args.mode, max_tasks=args.max_tasks,
                                   ttl=args.ttl, target=args.target_file, instruction=args.instruction)
    except (LeaseError, VerificationError, OSError, ValueError) as error:
        print(f"[ICARUS FAILED] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
