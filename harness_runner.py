"""Run the Teamchat test suite inside the teamchat-harness:test Docker image.

Usage: python harness_runner.py
Streams the container's stdout/stderr live and exits with its exit code.
Nothing is installed on the host; Docker must be installed and running.
"""
import shutil
import subprocess
import sys

IMAGE = "teamchat-harness:test"
COMMAND = ["docker", "run", "--rm", "--network", "none", "--read-only",
           "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
           "--tmpfs", "/tmp:rw,nosuid,nodev", IMAGE,
           "python", "docker/verify-and-test.py"]


def main() -> int:
    if shutil.which("docker") is None:
        print("BLOCKED: 'docker' not found on PATH (exit code 3).", file=sys.stderr)
        return 3

    print("Running:", " ".join(COMMAND), flush=True)
    try:
        # Inherit stdout/stderr so output streams live to the terminal.
        result = subprocess.run(COMMAND, check=False)
    except OSError as exc:
        print(f"ERROR: failed to start docker: {exc}", file=sys.stderr)
        return 3

    status = "PASS" if result.returncode == 0 else "FAIL"
    print(f"\nHARNESS {status}: exit code {result.returncode}", flush=True)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
