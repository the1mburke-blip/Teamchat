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
API credits. Before reading the target, the runner attempts
`git pull --rebase origin main` in the current directory. This requires a Git
repository with an `origin` remote and a `main` branch. Pull failures do not halt
task execution; exceptions such as a missing Git executable produce a warning.
The kernel rejects paths outside the current project and the
protected `.git`, `.github`, `dsh/cordis`, and `icarus/runtime` directories,
including case variants. Verification uses `pytest` when it is on PATH; otherwise
it compiles the target as Python and identifies this syntax-only mode explicitly.
Failed verification restores the original file or removes a newly created file.

## Icarus cloud execution

The canonical engine is `dsh/cordis/kernel.py`, with provider routing in
`dsh/provider.py` and task orchestration in `dsh/runner.py`.
Use the **Icarus Cloud Daemon** workflow in
`.github/workflows/icarus_cloud.yml` with `target_file` and `instruction` inputs.
The workflow binds both inputs through environment variables, runs the same
Cordis runner, and commits verified changes to `main`.

The legacy hourly runtime, its issue-comment gates, and its runtime-only
configuration have been retired. The separate Hermes skills query keeps its
prompt under `icarus/prompts/`. Existing app files, memory, receipts, and
repository history are preserved.

The root `.env` is local configuration and is excluded by `.gitignore` and from
downloadable bundles. Provision a separate `.env` before using a copied bundle.
To recreate the environment, create a Python virtual environment and install
`requirements-dev.txt` with its Python executable.
