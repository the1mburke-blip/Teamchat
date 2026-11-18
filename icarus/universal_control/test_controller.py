"""Deterministic controller tests; no model or credential access required."""
import tempfile
import unittest
from pathlib import Path

from controller import Icarus, Denied, DockerHarness, WorkerFailure


class Stub:
    def __init__(self, response=None, fails=False):
        self.response = response
        self.fails = fails

    def invoke(self, packet):
        if self.fails:
            raise WorkerFailure("simulated worker crash")
        return self.response(packet) if callable(self.response) else self.response


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.memory = root / "lineage"
        self.memory.mkdir()
        (self.memory / "identity.md").write_text("# ICARUS\n", encoding="utf-8")
        self.core = Icarus(root / "icarus-owned", self.memory)

    def test_replace_harness_same_task_and_verdict_owned_by_icarus(self):
        task = self.core.create_task("Write an approved note", allowed_note="PROOF")
        self.core.step(task, Stub({"type": "tool_request", "call_id": "a",
                                   "tool": "note.write", "args": {"text": "PROOF"},
                                   "verdict": "PASS"}), harness_name="A")
        continued = Icarus(self.core.state_root, self.memory)
        result = continued.step(task, Stub({"type": "final", "text": "complete",
                                            "verdict": "FAIL"}), harness_name="B")
        self.assertEqual(result["task_id"], task)
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["verdict"], "PASS")
        self.assertTrue(Path(result["evidence"]["path"]).is_file())

    def test_worker_cannot_award_pass_without_real_effect(self):
        task = self.core.create_task("Say hello", allowed_note="PROOF")
        result = self.core.step(task, Stub({"type": "final", "text": "success",
                                            "verdict": "PASS",
                                            "evidence": {"fake": True}}), harness_name="A")
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(result["state"], "AWAITING_EVIDENCE")

    def test_unapproved_tool_rejected(self):
        task = self.core.create_task("Task", allowed_note="PROOF")
        with self.assertRaises(Denied):
            self.core.step(task, Stub({"type": "tool_request", "call_id": "a",
                                       "tool": "shell.exec", "args": {"command": "whoami"}}),
                           harness_name="A")
        self.assertEqual(self.core.load(task)["state"], "REJECTED")

    def test_content_scope_cannot_expand(self):
        task = self.core.create_task("Task", allowed_note="PROOF")
        with self.assertRaises(Denied):
            self.core.step(task, Stub({"type": "tool_request", "call_id": "a",
                                       "tool": "note.write", "args": {"text": "OTHER"}}),
                           harness_name="A")
        self.assertFalse((self.core.notes / (task + ".txt")).exists())

    def test_replay_is_denied(self):
        task = self.core.create_task("Task", allowed_note="PROOF")
        call = {"type": "tool_request", "call_id": "a", "tool": "note.write",
                "args": {"text": "PROOF"}}
        self.core.step(task, Stub(call), harness_name="A")
        with self.assertRaises(Denied):
            self.core.step(task, Stub(call), harness_name="A")
        self.assertEqual(self.core.load(task)["events"][-1]["type"], "effect")

    def test_failure_preserves_task_across_restart(self):
        task = self.core.create_task("Task", allowed_note="PROOF")
        with self.assertRaises(WorkerFailure):
            self.core.step(task, Stub(fails=True), harness_name="A")
        recovered = Icarus(self.core.state_root, self.memory).load(task)
        self.assertEqual(recovered["state"], "WORKER_FAILED")
        self.assertEqual(recovered["task_id"], task)

    def test_identity_cannot_change_behind_task(self):
        task = self.core.create_task("Task")
        (self.memory / "identity.md").write_text("# DIFFERENT\n", encoding="utf-8")
        with self.assertRaises(Denied):
            Icarus(self.core.state_root, self.memory).load(task)

    def test_fail_closed_without_pinned_image(self):
        for spec in ["python:latest", "python@sha256:abc", ""]:
            with self.assertRaises(Denied):
                DockerHarness(spec)

    def test_invalid_worker_output_rejected(self):
        task = self.core.create_task("Task", allowed_note="PROOF")
        with self.assertRaises(Denied):
            self.core.step(task, Stub({"type": "whatever"}), harness_name="A")
        self.assertEqual(self.core.load(task)["state"], "REJECTED")


if __name__ == "__main__":
    unittest.main()
