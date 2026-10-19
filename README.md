# Cordis Kernel

Run commands from this project root. Python 3.12 and a local `.venv` are configured.
The provider loads `.env` from the current working directory without overriding
existing environment variables. OpenRouter takes precedence when its key is set;
otherwise the provider uses DeepSeek directly.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The test suite isolates provider calls using dummy credentials and mocked HTTP;
it does not spend API credits or display desktop notifications.

## Run a task

Activate the environment first so the Cordis kernel can locate `pytest`.

```powershell
.\.venv\Scripts\Activate.ps1
python -m dsh.runner sample.py "Create a Python function named add that returns the sum of two numbers."
```

If PowerShell activation is unavailable, set PATH for this terminal session:

```powershell
$env:Path = "$PWD\.venv\Scripts;$env:Path"
.\.venv\Scripts\python.exe -m dsh.runner sample.py "Create a Python function named add that returns the sum of two numbers."
```

Runner tasks make a real provider request using the configured key and can consume
API credits. The command-line runner now participates in the shared laptop/cloud
lease, requires a clean `main` checkout with writable `origin`, pulls with
`--ff-only`, and publishes its verified target. Existing Python callers of
`run_harness_task` retain best-effort synchronization and a filesystem lease;
they must pass a shared lease to coordinate with another machine.
The kernel rejects paths outside the current project and the
protected `.git`, `.github`, `dsh/cordis`, and `icarus/runtime` directories,
including case variants. Verification uses `pytest` when it is on PATH; otherwise
it compiles the target as Python and identifies this syntax-only mode explicitly.
Failed verification restores the original file or removes a newly created file.

## Icarus cloud execution

The canonical engine is `dsh/cordis/kernel.py`, with provider routing in
`dsh/provider.py` and task orchestration in `dsh/runner.py`.
Use the **Icarus Cloud Daemon** workflow in
`.github/workflows/icarus_cloud.yml`. Its default `goals` mode processes the
managed `GOAL.md` tasks below; `task` mode accepts `target_file` and `instruction`.
Inputs remain bound through environment variables. Only the declared target and
the coordinator's completion checkbox are staged; verified progress is published
after each task. No scheduler or live cloud run is enabled by this change.

### Managed goal format and local handoff

Keep explanatory checklists outside the managed block. Each managed line has one
relative target and a concrete instruction; malformed or empty blocks fail closed.
The coordinator, rather than the model, changes `[ ]` to `[x]` after the kernel's
integrity checks and tests succeed. Tasks must not target `GOAL.md`, the lease,
or protected kernel/workflow paths.

```markdown
<!-- icarus:tasks -->
- [ ] `sample.py` :: Implement add(a, b) returning their sum and preserve the existing API.
<!-- /icarus:tasks -->
```

On the laptop, from a clean checkout with Git authentication and pytest on PATH:

```powershell
python -m dsh.completion --owner laptop --max-tasks 20
```

Managed runs log outcomes without blocking desktop notification dialogs, so
they can continue unattended on Windows as well as on the cloud runner.

Dispatch the workflow in `goals` mode for cloud continuation. One run processes
up to `max_tasks` (default 20, maximum 100), or stops on the first failure. Exit 2
means published progress exists but tasks remain; dispatch again to resume.
An active laptop lease makes cloud yield with no model call. A subsequent dispatch
can take over after the laptop stops heartbeating; this is not an always-running
offline detector. Already completed tasks do not trigger another model request.

### Lease protocol

The kernel's `.icarus_lease.lock` is an OS-locked record on a shared filesystem.
Managed CLI execution instead uses `origin`'s isolated `icarus-lease` branch as
the cross-machine authority, mirroring its record locally in the ignored lock.
The default expiry is 300 seconds with renewal every 100 seconds. Workers need
synchronized clocks and the same authenticated, writable origin. Different
filesystem lock files alone cannot coordinate different machines.

Remote updates use explicit revision comparisons. Publishing `main` and renewing
the lease happen in one atomic push; a takeover or non-fast-forward main update
rejects publication. `main` is never force-pushed. Network/authentication failures
stop work, not permission to assume the laptop is offline. A stale owner cannot
renew or release a replacement owner's token. Abrupt process death leaves a lease
that expires; normal completion/failure releases it. Errors after a local commit
retain that commit for recovery and refuse further runs until main is synchronized.

These are cooperative safeguards for the managed entry points; arbitrary external
DSH tools do not acquire this lease automatically. Goal completion means the
declared file passed the kernel and project tests, not independent proof of host
plugin activation or the correctness of every possible requirement.

Non-Git folders remain supported by `python -m dsh.runner`: they use only the
filesystem lease and original local verification/rollback, with no cloud sync
or publication. Use the shared completion command for cross-machine handoff.

The legacy hourly runtime, its issue-comment gates, and its runtime-only
configuration have been retired. The separate Hermes skills query keeps its
prompt under `icarus/prompts/`. Existing app files, memory, receipts, and
repository history are preserved.

The root `.env` is local configuration and is excluded by `.gitignore` and from
downloadable bundles. Provision a separate `.env` before using a copied bundle.
To recreate the environment, create a Python virtual environment and install
`requirements-dev.txt` with its Python executable.

# Cloud Kernel Test Pass
