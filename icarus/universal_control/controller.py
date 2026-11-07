"""ICARUS-controlled harness execution. Standard library; no worker authority.

This is an isolated candidate, not installed on the owner's machine.
A Docker backend is mandatory: no unsandboxed local subprocess fallback.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid


class Denied(PermissionError):
    pass


class WorkerFailure(RuntimeError):
    pass


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class DockerHarness:
    """Runs a prebuilt harness-adapter image without host resources or network.

    Only an exact, locally present image content ID is accepted. No host mounts,
    credentials, Docker socket, mutable image tags or network are passed.
    """

    def __init__(self, image_id: str, *, executable="docker"):
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", image_id):
            raise Denied("Unpinned or invalid worker image ID")
        self.image_id = image_id
        self.executable = executable

    def invoke(self, task_packet: dict):
        argv = [
            self.executable, "run", "--rm", "--pull=never",
            "--network=none", "--read-only",
            "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--pids-limit=64", "--memory=256m", "--cpus=1",
            "--user=65534:65534", "--tmpfs=/tmp:rw,nosuid,noexec,size=16m",
            "-i", self.image_id,
        ]
        try:
            proc = subprocess.run(
                argv, input=_canonical(task_packet) + "\n", text=True,
                capture_output=True, timeout=45, check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            raise WorkerFailure("Sandbox unavailable or timed out") from e
        if proc.returncode != 0:
            raise WorkerFailure(f"Sandbox worker exited {proc.returncode}")
        try:
            reply = json.loads(proc.stdout)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise WorkerFailure("Invalid sandbox worker response") from e
        if not isinstance(reply, dict):
            raise WorkerFailure("Worker response must be an object")
        return reply


class Icarus:
    """The only owner of task IDs, memory, tool admission and final verdicts."""

    def __init__(self, state_root: Path, lineage_root: Path):
        self.state_root = Path(state_root).resolve()
        self.lineage_root = Path(lineage_root).resolve()
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.tasks = self.state_root / "tasks"
        self.notes = self.state_root / "notes"
        self.tasks.mkdir(exist_ok=True)
        self.notes.mkdir(exist_ok=True)
        identity = self.lineage_root / "identity.md"
        if not identity.is_file():
            raise Denied("ICARUS identity not found; refusing startup")
        self.identity_hash = hashlib.sha256(identity.read_bytes()).hexdigest()

    def _path(self, task_id):
        if not re.fullmatch(r"[a-f0-9]{32}", task_id):
            raise Denied("Invalid task ID")
        return self.tasks / (task_id + ".json")

    def _write_state(self, task):
        dest = self._path(task["task_id"])
        fd, name = tempfile.mkstemp(prefix=".icarus-", dir=self.tasks)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(_canonical(task) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, dest)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def load(self, task_id):
        task = json.loads(self._path(task_id).read_text(encoding="utf-8"))
        if task["identity_hash"] != self.identity_hash:
            raise Denied("Identity changed since task creation")
        return task

    def create_task(self, objective: str, *, allowed_note: str | None = None):
        if not objective.strip() or len(objective) > 20000:
            raise ValueError("Invalid task objective")
        task_id = uuid.uuid4().hex
        task = {
            "task_id": task_id, "identity_hash": self.identity_hash,
            "objective": objective, "expected_note": allowed_note,
            "state": "READY", "events": [], "calls": [],
            "result": None, "evidence": None, "verdict": "FAIL",
        }
        self._write_state(task)
        return task_id

    def _verify_note(self, task):
        expected = task["expected_note"]
        if expected is None:
            return None
        dest = self.notes / (task["task_id"] + ".txt")
        if not dest.is_file() or dest.read_text(encoding="utf-8") != expected:
            return None
        return {"path": str(dest), "sha256": hashlib.sha256(dest.read_bytes()).hexdigest()}

    def step(self, task_id: str, harness, *, harness_name: str):
        task = self.load(task_id)
        if task["state"] in ("PASS", "REJECTED"):
            raise Denied("Terminal task cannot be re-executed")
        packet = {
            "protocol": "icarus.worker.v1", "task_id": task_id,
            "objective": task["objective"],
            "observations": [x for x in task["events"] if x["type"] == "effect"],
        }
        try:
            reply = harness.invoke(packet)
        except WorkerFailure:
            task["state"] = "WORKER_FAILED"
            task["events"].append({"type": "worker_failure", "harness": harness_name})
            self._write_state(task)
            raise
        kind = reply.get("type")
        if kind == "tool_request":
            call_id, tool, args = reply.get("call_id"), reply.get("tool"), reply.get("args")
            if not isinstance(call_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", call_id):
                raise Denied("Invalid worker call ID")
            key = harness_name + ":" + call_id
            if key in task["calls"]:
                raise Denied("Replayed worker call")
            # Record each request before admission, including denials.
            task["calls"].append(key)
            if tool != "note.write" or not isinstance(args, dict) or set(args) != {"text"}:
                task["state"] = "REJECTED"
                task["events"].append({"type": "denied", "reason": "UNAUTHORIZED_TOOL"})
                self._write_state(task)
                raise Denied("Unauthorized tool")
            expected = task["expected_note"]
            if expected is None or args["text"] != expected:
                task["state"] = "REJECTED"
                task["events"].append({"type": "denied", "reason": "SCOPE_MISMATCH"})
                self._write_state(task)
                raise Denied("Target or content outside owner authorization")
            dest = self.notes / (task_id + ".txt")
            if dest.exists():
                task["state"] = "REJECTED"
                self._write_state(task)
                raise Denied("Duplicate effect; no overwrite")
            fd, name = tempfile.mkstemp(prefix=".effect-", dir=self.notes)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    stream.write(expected)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(name, dest)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
            evidence = self._verify_note(task)
            if evidence is None:
                task["state"] = "OUTCOME_UNKNOWN"
                self._write_state(task)
                raise WorkerFailure("Effect cannot be independently verified")
            task["events"].append({"type": "effect", "tool": "note.write",
                                   "evidence_hash": evidence["sha256"]})
            task["evidence"] = evidence
            task["state"] = "WORKING"
        elif kind == "final":
            # Ignore worker-supplied verdict and proof. Trusted readback decides.
            task["result"] = str(reply.get("text", ""))[:8000]
            task["evidence"] = self._verify_note(task)
            task["verdict"] = "PASS" if task["evidence"] is not None else "FAIL"
            task["state"] = task["verdict"] if task["evidence"] else "AWAITING_EVIDENCE"
            task["events"].append({"type": "final", "harness": harness_name,
                                   "verdict": task["verdict"]})
        else:
            task["state"] = "REJECTED"
            task["events"].append({"type": "denied", "reason": "INVALID_PROTOCOL"})
            self._write_state(task)
            raise Denied("Invalid worker protocol response")
        self._write_state(task)
        return task
