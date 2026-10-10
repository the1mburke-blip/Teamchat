"""Disposable adapter fixture: two interchangeable workers with one JSON protocol.

No host tools or credentials are available in the sandbox. This is a test
worker, not a claim that DSH/Hermes production adapters are installed.
"""
import json
import os
import socket
import sys
from pathlib import Path


def main():
    request = json.loads(sys.stdin.readline())
    if request.get("protocol") != "icarus.worker.v1":
        raise SystemExit("unsupported protocol")
    mode = os.environ.get("HARNESS_MODE", "")
    if mode == "A":
        # The worker can only REQUEST that the ICARUS broker perform an effect.
        answer = {"type": "tool_request", "call_id": "fixture-once",
                  "tool": "note.write", "args": {"text": "PROOF"},
                  "verdict": "PASS"}
    elif mode == "B":
        if not request.get("observations"):
            raise SystemExit("cannot finalize without a broker observation")
        answer = {"type": "final", "text": "Replacement worker completed task",
                  "verdict": "PASS"}
    elif mode == "ATTACK":
        can_read_host = Path("/icarus-protected-host-secret").exists()
        network_open = False
        try:
            with socket.create_connection(("1.1.1.1", 53), timeout=2):
                network_open = True
        except OSError:
            pass
        answer = {"type": "final", "text": "Host access=%s, network=%s" %
                  (can_read_host, network_open), "verdict": "PASS",
                  "probe": {"host_readable": can_read_host, "network_open": network_open}}
    else:
        raise SystemExit("unsupported harness mode")
    print(json.dumps(answer))


if __name__ == "__main__":
    main()
