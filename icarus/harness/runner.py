#!/usr/bin/env python3
"""Deterministic evidence gate; Python 3.9+, standard library only.

Usage: python harness-runner.py [task.json|-] (default: stdin).
Commands are argv lists or shell-like strings, executed WITHOUT a shell.
Paths are relative to the runner's current working directory.
Explicit tool/mutation assignments set requires_tools/requires_state_mutation
and execution_receipt (path to a trusted supervisor's dispatcher receipt).
These flags require event/count/task-ID validation as well as artifact readback.
Use --validate-execution task.json receipt.json for admission-only checks, or
--test-suite for the offline Python and Apps Script regression suite.

Use --route-task routing.json attempts_dir for the supervised operating loop.
The trusted supervisor supplies a task, target_chair, seat_availability,
availability_expires_at (UTC), and allow_pilot (boolean). An available target
returns a delegation decision (exit 4). Pilot admission requires all four seats
to be explicitly unavailable and an unused task ID in the durable attempt store.
Exit 0 in pilot mode returns physical evidence for a separate adjudicator.

Readback schemas (no additional keys):
  {"type":"file_hash", "path":"result.bin", "expected_hash":"<64 hex digits>"}
  {"type":"ledger_row", "path":"ledger.jsonl", "row_id":"task-1",
   "required_fields":["id","result"]}
Ledger IDs use the literal top-level "id" field; exactly one match is required.

Exit codes: 0 verified, 1 execution/readback failure, 2 invalid/zero-value
packet, 3 environmental or authorization blocker. Command output is captured,
never forwarded to stdout. Diagnostics are JSON on stderr, except code 3,
which uses the mandatory two-line escalation format.

Trust boundary: run under a trusted supervisor with a trusted input packet.
Subprocess separation is NOT a security sandbox. This file cannot prevent a
same-user command from modifying operational state, this script, or evidence.
The host must independently restrict writes and accept completion only through
this gate's exit status AND parsed verdict. The hash must come from a trusted
source; field presence alone does not attest ledger truth or artifact freshness.
"""

import datetime
import hashlib
import hmac
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from dsh.execution_integrity import ExecutionRejected, validate_execution


REQUIRED = frozenset({"task_id", "cost_tier", "decision_changing",
                      "owner_preauthorized", "command", "readback"})
OPTIONAL = frozenset({"requires_tools", "requires_state_mutation", "execution_receipt"})
MAX_INPUT_BYTES = 1024 * 1024
MAX_LEDGER_LINE_BYTES = 1024 * 1024
COMMAND_TIMEOUT_SECONDS = 300
DIAGNOSTIC_BYTES = 16384
SPECIALISTS = frozenset({"CODEX", "SOL", "LUNA", "GRACE"})
ROUTING_FIELDS = frozenset({"task", "target_chair", "seat_availability",
                            "availability_expires_at", "allow_pilot"})


class InvalidPacket(ValueError):
    pass


class EvidenceFailure(ValueError):
    pass


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidPacket("Duplicate JSON key: " + key)
        result[key] = value
    return result


def reject_constant(value):
    raise InvalidPacket("Non-finite JSON constant: " + value)


def parse_json(data):
    return json.loads(data, object_pairs_hook=unique_object,
                      parse_constant=reject_constant)


def valid_string(value):
    return (isinstance(value, str) and "\0" not in value
            and not any(0xD800 <= ord(char) <= 0xDFFF for char in value))


def nonempty_string(value):
    return valid_string(value) and bool(value.strip())


def validate(packet):
    if not isinstance(packet, dict) or not REQUIRED <= set(packet) or set(packet) - REQUIRED - OPTIONAL:
        raise InvalidPacket("Task must contain exactly: " + ", ".join(sorted(REQUIRED)))
    for name in ("requires_tools", "requires_state_mutation"):
        if name in packet and type(packet[name]) is not bool:
            raise InvalidPacket(name + " must be boolean")
    if "execution_receipt" in packet and not nonempty_string(packet["execution_receipt"]):
        raise InvalidPacket("execution_receipt must be a path")
    if not nonempty_string(packet["task_id"]):
        raise InvalidPacket("task_id must be a nonempty string")
    if packet["decision_changing"] is not True:
        raise InvalidPacket("decision_changing must be true")
    if type(packet["owner_preauthorized"]) is not bool:
        raise InvalidPacket("owner_preauthorized must be boolean")
    if not isinstance(packet["cost_tier"], str) or packet["cost_tier"] not in {
            "LOW", "MEDIUM", "HIGH"}:
        raise InvalidPacket("Invalid cost_tier")
    command = packet["command"]
    if isinstance(command, str):
        if not nonempty_string(command):
            raise InvalidPacket("command must not be empty")
        try:
            command = shlex.split(command, posix=True)
        except ValueError as exc:
            raise InvalidPacket(str(exc)) from exc
    if not isinstance(command, list) or not command:
        raise InvalidPacket("command must be a string or nonempty argv list")
    if not nonempty_string(command[0]) or any(
            not valid_string(arg) for arg in command):
        raise InvalidPacket("command arguments must be Unicode strings without NUL bytes")
    spec = packet["readback"]
    if not isinstance(spec, dict):
        raise InvalidPacket("readback must be an object")
    kind = spec.get("type")
    if kind == "file_hash":
        keys = {"type", "path", "expected_hash"}
        expected = spec.get("expected_hash")
        if not isinstance(expected, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", expected):
            raise InvalidPacket("expected_hash must contain 64 hexadecimal digits")
    elif kind == "ledger_row":
        keys = {"type", "path", "row_id", "required_fields"}
        if not nonempty_string(spec.get("row_id")):
            raise InvalidPacket("row_id must be a nonempty string")
        fields = spec.get("required_fields")
        if (not isinstance(fields, list) or not fields
                or any(not nonempty_string(field) for field in fields)
                or len(set(fields)) != len(fields)):
            raise InvalidPacket("required_fields must be unique nonempty strings")
    else:
        raise InvalidPacket("Unsupported readback type")
    if set(spec) != keys or not nonempty_string(spec.get("path")):
        raise InvalidPacket("Invalid readback keys or path")
    return command


def emit_diagnostic(payload):
    sys.stderr.write(json.dumps(payload, ensure_ascii=True, allow_nan=False) + "\n")
    sys.stderr.flush()


def escalate(action, error):
    # Escape untrusted newlines so escalation always consists of exactly two lines.
    detail = json.dumps(str(error), ensure_ascii=True)[1:-1]
    sys.stderr.write("OWNER ASSISTANCE REQUIRED — " + action + "\n"
                     "Blocked On: " + detail + "\n")
    sys.stderr.flush()
    return 3


def capture_tail(stream):
    size = stream.seek(0, os.SEEK_END)
    stream.seek(max(0, size - DIAGNOSTIC_BYTES))
    return {"text": stream.read().decode("utf-8", errors="replace"),
            "bytes": size, "truncated": size > DIAGNOSTIC_BYTES}


def execute(command):
    # Disk-backed captures avoid retaining unbounded child output in memory.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        started = time.monotonic()
        timed_out = False
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL,
                                    stdout=stdout, stderr=stderr, shell=False,
                                    timeout=COMMAND_TIMEOUT_SECONDS, check=False)
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            exit_code = None
        return {"exit_code": exit_code,
                "duration_seconds": round(time.monotonic() - started, 6),
                "timed_out": timed_out,
                "stdout": capture_tail(stdout), "stderr": capture_tail(stderr)}


def fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def verify(spec):
    path = Path(spec["path"])
    try:
        # O_NONBLOCK prevents a FIFO/device from blocking before regular-file validation.
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
        descriptor = os.open(path, flags)
    except (FileNotFoundError, NotADirectoryError, IsADirectoryError) as exc:
        raise EvidenceFailure(str(exc)) from exc
    with os.fdopen(descriptor, "rb") as artifact:
        before = os.fstat(artifact.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise EvidenceFailure("Readback target must be a regular file")
        if spec["type"] == "file_hash":
            digest = hashlib.sha256()
            for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
                digest.update(chunk)
            actual = digest.hexdigest()
            if not hmac.compare_digest(actual, spec["expected_hash"].lower()):
                raise EvidenceFailure("SHA-256 mismatch: " + actual)
        else:
            matches = 0
            line_number = 0
            while True:
                line = artifact.readline(MAX_LEDGER_LINE_BYTES + 1)
                if not line:
                    break
                line_number += 1
                if len(line) > MAX_LEDGER_LINE_BYTES:
                    raise EvidenceFailure("Ledger line exceeds size limit")
                if not line.strip():
                    continue
                try:
                    row = parse_json(line.decode("utf-8"))
                except (ValueError, UnicodeError, RecursionError) as exc:
                    raise EvidenceFailure("Invalid ledger JSON at line " + str(line_number)) from exc
                if not isinstance(row, dict):
                    raise EvidenceFailure("Ledger row must be an object")
                if row.get("id") == spec["row_id"]:
                    matches += 1
                    missing = [field for field in spec["required_fields"] if field not in row]
                    if missing:
                        raise EvidenceFailure("Missing ledger fields: " + ", ".join(missing))
            if matches != 1:
                raise EvidenceFailure("Expected exactly one ledger row; found " + str(matches))
        after = os.fstat(artifact.fileno())
        try:
            # Path and handle stat can disagree on Windows for the same file.
            with os.fdopen(os.open(path, flags), "rb") as reopened:
                current = os.fstat(reopened.fileno())
        except (FileNotFoundError, NotADirectoryError) as exc:
            raise EvidenceFailure("Artifact disappeared during readback") from exc
        if (not stat.S_ISREG(current.st_mode) or fingerprint(before) != fingerprint(after)
                or fingerprint(after) != fingerprint(current)):
            raise EvidenceFailure("Artifact changed during readback")
    return str(path.absolute())


def load_packet(source):
    if source == "-":
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    else:
        with open(source, "rb") as stream:
            raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise InvalidPacket("Task input exceeds size limit")
    return parse_json(raw.decode("utf-8"))


def main():
    if len(sys.argv) > 2:
        emit_diagnostic({"verdict": "HALT_ZERO_VALUE", "reason": "Expected one task file or stdin"})
        return 2
    source = sys.argv[1] if len(sys.argv) == 2 else "-"
    try:
        packet = load_packet(source)
        command = validate(packet)
    except OSError as exc:
        return escalate("Make the task input readable by the runner account.", exc)
    except (ValueError, UnicodeError, RecursionError) as exc:
        emit_diagnostic({"verdict": "HALT_ZERO_VALUE", "reason": str(exc)})
        return 2
    if not packet["owner_preauthorized"]:
        return escalate("Authorize this task in a trusted task packet.",
                        "owner_preauthorized is false")
    return run_task(packet, command)


def validate_routing(route):
    if not isinstance(route, dict) or set(route) != ROUTING_FIELDS:
        raise InvalidPacket("Invalid supervised routing fields")
    target = route["target_chair"]
    seats = route["seat_availability"]
    expires = route["availability_expires_at"]
    if not isinstance(target, str) or target not in SPECIALISTS:
        raise InvalidPacket("Invalid target chair")
    if (not isinstance(seats, dict) or set(seats) != SPECIALISTS
            or any(status not in ("available", "unavailable", "unknown") for status in seats.values())):
        raise InvalidPacket("Expected an explicit availability status for each specialist")
    if type(route["allow_pilot"]) is not bool:
        raise InvalidPacket("allow_pilot must be boolean")
    if not isinstance(expires, str) or not expires.endswith(("Z", "+00:00")):
        raise InvalidPacket("Expected a UTC availability expiry")
    if expires.endswith("Z"):
        expires = expires[:-1] + "+00:00"
    expiry = datetime.datetime.fromisoformat(expires)
    if expiry.utcoffset() != datetime.timedelta(0):
        raise InvalidPacket("Expected a timezone-aware UTC availability expiry")
    packet = route["task"]
    command = validate(packet)
    return packet, command, expiry


def route_task(source, attempts_dir):
    try:
        route = load_packet(source)
        packet, command, expiry = validate_routing(route)
    except OSError as exc:
        return escalate("Provide a readable trusted routing packet.", exc)
    except (ValueError, UnicodeError, RecursionError) as exc:
        emit_diagnostic({"verdict": "HALT_ZERO_VALUE", "reason": str(exc)})
        return 2

    now = datetime.datetime.now(datetime.timezone.utc)
    if not packet["owner_preauthorized"] or expiry <= now:
        return escalate("Refresh the authorized routing packet.",
                        "Missing owner authorization or expired availability")
    target = route["target_chair"]
    seats = route["seat_availability"]
    task_id = packet["task_id"]
    if seats[target] == "available":
        print(json.dumps({"task_id": task_id, "route": "DELEGATE", "target_chair": target}), flush=True)
        return 4
    if any(status != "unavailable" for status in seats.values()):
        return escalate("Resolve specialist routing before considering pilot execution.",
                        "All specialist seats must be confirmed unavailable")
    if not route["allow_pilot"] or packet["readback"]["type"] != "file_hash":
        return escalate("Supply an authorized pilot command and independent SHA-256 target.",
                        "Pilot authorization and file_hash readback are required")

    # Reserve before any subprocess effect. An interrupted attempt stays reserved.
    name = hashlib.sha256(task_id.encode("utf-8")).hexdigest() + ".json"
    try:
        with (Path(attempts_dir) / name).open("x", encoding="utf-8") as marker:
            json.dump({"task_id": task_id, "reserved_at_utc": now.isoformat()}, marker)
            marker.flush()
            os.fsync(marker.fileno())
    except FileExistsError:
        return escalate("Hand the task back for adjudication.", "Harness Pilot attempt already reserved")
    except OSError as exc:
        return escalate("Provide a writable durable pilot attempt store.", exc)
    return run_task(packet, command, pilot=True)


def run_task(packet, command, *, pilot=False):
    try:
        execution = execute(command)
    except OSError as exc:
        return escalate("Make the command executable in the runner environment.", exc)
    except KeyboardInterrupt:
        emit_diagnostic({"task_id": packet["task_id"], "verdict": "FAIL",
                         "reason": "Execution interrupted"})
        return 1
    if execution["exit_code"] != 0:
        emit_diagnostic({"task_id": packet["task_id"], "verdict": "FAIL",
                         "reason": "Command timed out" if execution["timed_out"] else "Command failed",
                         "execution": execution})
        return 1
    try:
        if packet.get("execution_receipt") or packet.get("requires_tools") or packet.get("requires_state_mutation"):
            if not packet.get("execution_receipt"):
                raise EvidenceFailure("EXECUTION_RECEIPT_REQUIRED")
            with open(packet["execution_receipt"], "rb") as stream:
                raw_receipt = stream.read(MAX_INPUT_BYTES + 1)
            if len(raw_receipt) > MAX_INPUT_BYTES:
                raise EvidenceFailure("EXECUTION_RECEIPT_TOO_LARGE")
            validate_execution(packet, parse_json(raw_receipt.decode("utf-8")))
        proof = verify(packet["readback"])
    except (EvidenceFailure, ExecutionRejected, ValueError, UnicodeError) as exc:
        emit_diagnostic({"task_id": packet["task_id"], "verdict": "FAIL",
                         "reason": str(exc), "execution": execution})
        return 1
    except OSError as exc:
        return escalate("Make the readback artifact readable by the runner account.", exc)
    except KeyboardInterrupt:
        emit_diagnostic({"task_id": packet["task_id"], "verdict": "FAIL",
                         "reason": "Readback interrupted"})
        return 1
    if pilot:
        print(json.dumps({"task_id": packet["task_id"], "route": "HARNESS_PILOT",
                          "verdict": "VERIFYING", "exit_code": execution["exit_code"],
                          "proof_artifact": proof, "sha256": packet["readback"]["expected_hash"].lower()}),
              flush=True)
        return 0
    # The legacy evidence-only interface retains its original verdict format.
    sys.stdout.write(json.dumps({"evaluator": "CHAIR_JUDGE", "task_id": packet["task_id"],
                                 "verdict": "PASS", "proof_artifact": proof,
                                 "readback_status": "VERIFIED"}, ensure_ascii=True) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--route-task":
        sys.exit(route_task(sys.argv[2], sys.argv[3]))
    if sys.argv[1:] == ["--test-suite"]:
        sys.exit(subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "tests/"],
                                cwd=Path(__file__).resolve().parents[2], check=False).returncode)
    if len(sys.argv) == 4 and sys.argv[1] == "--validate-execution":
        try:
            inputs = []
            for name in sys.argv[2:]:
                with open(name, "rb") as stream:
                    raw = stream.read(MAX_INPUT_BYTES + 1)
                if len(raw) > MAX_INPUT_BYTES:
                    raise ExecutionRejected("EXECUTION_INPUT_TOO_LARGE")
                inputs.append(parse_json(raw.decode("utf-8")))
            validate_execution(*inputs)
        except (OSError, ValueError, UnicodeError, RecursionError) as error:
            emit_diagnostic({"verdict": "FAIL", "reason": str(error)})
            sys.exit(1)
        sys.exit(0)
    if len(sys.argv) == 4 and sys.argv[1] == "--receipt-from-run":
        from dsh.state_write_gate import receipt_from_run
        try:
            receipt_from_run(int(sys.argv[2]), sys.argv[3])
        except (OSError, ValueError, KeyError, TypeError) as error:
            emit_diagnostic({"verdict": "FAIL", "reason": str(error)})
            sys.exit(1)
        sys.exit(0)
    if sys.argv[1:] == ["--audit-state-writes"]:
        from dsh.state_write_gate import audit_cli
        sys.exit(audit_cli())
    if len(sys.argv) == 3 and sys.argv[1] == "--write-ci-manifest":
        from dsh.state_write_gate import write_manifest
        try:
            write_manifest(sys.argv[2])
        except (OSError, ValueError, KeyError) as error:
            sys.exit(escalate("Provide a successful GitHub harness execution context.", error))
        sys.exit(0)
    sys.exit(main())
