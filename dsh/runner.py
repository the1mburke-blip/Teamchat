import pathlib
import re
import subprocess
import sys
from dsh.cordis.kernel import CordisKernel
from dsh.provider import call_llm_raw, format_code_prompt


def sync_repository_state():
    """Syncs local repository state with origin/main before executing tasks."""
    try:
        subprocess.run(
            ["git", "pull", "--rebase", "origin", "main"],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as e:
        print(f"[DSH SYNC WARNING] Could not auto-sync repository: {e}", file=sys.stderr)


def extract_code_block(raw_response: str) -> str:
    lines = raw_response.strip().splitlines(keepends=True)
    if len(lines) >= 2:
        opening = re.fullmatch(r"(`{3,}|~{3,})[^\r\n]*\r?\n", lines[0])
        if opening:
            fence = opening.group(1)
            closing = lines[-1].strip()
            if len(closing) >= len(fence) and set(closing) == {fence[0]}:
                return "".join(lines[1:-1])
    return raw_response.strip()


def run_harness_task(target_file: str, instruction: str, *, lease=None, sync=True):
    # Pull latest cloud state before running
    if sync:
        sync_repository_state()

    kernel = CordisKernel(workspace_root=".", lease=lease, notify=lease is None)
    kernel.validate_path(target_file)
    if lease is not None:
        lease.assert_owned()

    p = pathlib.Path(target_file)
    current_code = p.read_text(encoding="utf-8") if p.is_file() else ""

    prompt = format_code_prompt(current_code, instruction)
    print(f"[DSH RUNNER] Dispatching task to model for {target_file}...")

    raw_response = call_llm_raw(prompt)
    clean_patch = extract_code_block(raw_response)

    print("[DSH RUNNER] Patch received. Passing directly to CordisKernel...")
    kernel.apply_and_verify(target_file, clean_patch)


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) < 2:
        print("Usage: python -m dsh.runner <target_file> <instruction>")
        return 1
    try:
        repository = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True,
        )
        in_git = repository.returncode == 0 and repository.stdout.strip() == "true"
    except OSError:
        in_git = False
    if not in_git:
        run_harness_task(arguments[0], arguments[1])
        return 0
    from dsh.completion import main as completion_main
    return completion_main([
        "--mode", "task", "--target-file", arguments[0], "--instruction", arguments[1],
    ])


if __name__ == "__main__":
    sys.exit(main())
