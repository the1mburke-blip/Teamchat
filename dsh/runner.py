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


def run_harness_task(target_file: str, instruction: str):
    # Pull latest cloud state before running
    sync_repository_state()

    kernel = CordisKernel(workspace_root=".")
    kernel.validate_path(target_file)

    p = pathlib.Path(target_file)
    current_code = p.read_text(encoding="utf-8") if p.is_file() else ""

    prompt = format_code_prompt(current_code, instruction)
    print(f"[DSH RUNNER] Dispatching task to model for {target_file}...")

    raw_response = call_llm_raw(prompt)
    clean_patch = extract_code_block(raw_response)

    print("[DSH RUNNER] Patch received. Passing directly to CordisKernel...")
    kernel.apply_and_verify(target_file, clean_patch)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m dsh.runner <target_file> <instruction>")
        sys.exit(1)

    run_harness_task(sys.argv[1], sys.argv[2])
