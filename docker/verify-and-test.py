"""Verify actual container restrictions before running the offline suite."""
import errno
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    try:
        status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines() if ":" in line)
        if os.geteuid() == 0 or int(status["CapEff"].strip(), 16) != 0 or status["NoNewPrivs"].strip() != "1":
            raise RuntimeError("non-root/capability/no-new-privileges restriction missing")
        routes = Path("/proc/net/route").read_text().splitlines()[1:]
        if any(line.split()[1] == "00000000" for line in routes):
            raise RuntimeError("unexpected default network route")
        probe = Path("/app/.icarus-container-write-probe")
        try:
            with probe.open("x") as stream:
                stream.write("unexpected writable application filesystem")
        except OSError as error:
            if error.errno != errno.EROFS:
                raise RuntimeError("application root is not proven read-only") from error
        else:
            probe.unlink()
            raise RuntimeError("application filesystem is writable")
        print(json.dumps({"container_preflight": "VERIFIED", "uid": os.geteuid(),
                          "capabilities": 0, "no_new_privileges": True,
                          "application_read_only": True, "default_route": False}), flush=True)
    except (OSError, KeyError, ValueError, RuntimeError) as error:
        print("BLOCKED: container verification failed: " + str(error), file=sys.stderr)
        return 3
    return subprocess.run([sys.executable, "harness-runner.py", "--test-suite"], check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
