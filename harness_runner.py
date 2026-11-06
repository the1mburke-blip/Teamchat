"""Run the Teamchat test suite inside the teamchat-harness:test Docker image.

Usage: python harness_runner.py
Streams the container's stdout/stderr live and exits with its exit code.
Nothing is installed on the host; Docker must be installed and running.
"""
import shutil
import subprocess
import sys

IMAGE = "teamchat-harness:test"
COMMAND = ["docker", "run", "--rm", IMAGE, "python", "-m", "pytest", "tests/"]


def main() -> int:
    if shutil.which("docker") is None:
        print("ERROR: 'docker' not found on PATH.", file=sys.stderr)
        return 127

    print("Running:", " ".join(COMMAND), flush=True)
    try:
        # Inherit stdout/stderr so output streams live to the terminal.
        result = subprocess.run(COMMAND, check=False)
    except OSError as exc:
        print(f"ERROR: failed to start docker: {exc}", file=sys.stderr)
        return 126

    status = "PASS" if result.returncode == 0 else "FAIL"
    print(f"\nHARNESS {status}: exit code {result.returncode}", flush=True)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
