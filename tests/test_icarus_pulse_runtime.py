import io
import json
import os
import tempfile
import unittest
from contextlib import chdir, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from icarus.core import runtime
from icarus.runtime import icarus_run as legacy_runtime


class PulseRuntimeTests(unittest.TestCase):
    def test_legacy_runtime_module_reexports_packaged_implementation(self):
        self.assertIs(legacy_runtime.main, runtime.main)

    def test_owner_command_prefixes_are_normalized_without_losing_task_fields(self):
        cases = [
            ("ICARUS_RUN Review the board\nVERIFY_FILE: STATUS.md", "Review the board\nVERIFY_FILE: STATUS.md"),
            ("[ICARUS SUPERVISORY DIRECTIVE] Inspect the agents", "Inspect the agents"),
            ("[SOL] MULTI-AGENT INTERACTION AUDIT — REQUESTED BY MICHAEL\nMODEL: gemini-3.1-flash-lite",
             "MULTI-AGENT INTERACTION AUDIT — REQUESTED BY MICHAEL\nMODEL: gemini-3.1-flash-lite"),
            ("[sol] Review this\nVERIFY_URL: https://github.com/example/Teamchat",
             "Review this\nVERIFY_URL: https://github.com/example/Teamchat"),
            ("**[SOL] MULTI-AGENT INTERACTION AUDIT — REQUESTED BY MICHAEL**\nMODEL: gemini-3.1-flash-lite",
             "MULTI-AGENT INTERACTION AUDIT — REQUESTED BY MICHAEL\nMODEL: gemini-3.1-flash-lite"),
            ("**[SOL]** Review this\nVERIFY_FILE: STATUS.md",
             "Review this\nVERIFY_FILE: STATUS.md"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(runtime.normalize_owner_command(raw), expected)
        self.assertIsNone(runtime.normalize_owner_command("ordinary conversation"))

    def setUp(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(chdir(root))
        self.output = root / "github-output"
        self.reservation = root / "icarus-pulse-reservation.json"
        self.enterContext(patch.dict(os.environ, {
            "GITHUB_EVENT_NAME": "schedule", "GITHUB_REF": "refs/heads/main",
            "GITHUB_RUN_ID": "101", "PULSE_RESERVATION_ID": "201",
            "GITHUB_OUTPUT": str(self.output), "RUNNER_TEMP": str(root),
        }))
        self.enterContext(patch.multiple(runtime, GH_TOKEN="test-token", REPO="example/Teamchat"))
        self.day = runtime.NOW.date().isoformat()
        self.duty = {
            "timestamp_utc": runtime.NOW.isoformat(), "monitoring_result": "SUCCESS",
            "backlog_claim": {"issue_number": 12},
            "dispatch_receipts": [{"issue_number": 12, "task_id": "BACKLOG-12", "delegated_to": "[SOL]",
                                   "dispatch_comment_id": 301}],
        }
        self.write_duty()

    def write_duty(self):
        Path("RUN_LOG.jsonl").write_text(json.dumps(self.duty) + "\n", encoding="utf-8")

    def test_tenth_receipt_stops_cleanly_before_reservation(self):
        with patch.object(runtime, "pulse_artifacts", return_value=[{}] * 10) as artifacts:
            with redirect_stdout(io.StringIO()) as output:
                self.assertIsNone(runtime.pulse_reserve())
        artifacts.assert_called_once_with("artifacts", f"icarus-pulse-quota-{self.day}")
        self.assertEqual(output.getvalue().strip(),
                         "[QUOTA_GATE: DAILY PARTITION LIMIT REACHED (10/10) - INFERENCE SKIPPED]")
        self.assertFalse(self.reservation.exists())
        self.assertFalse(self.output.exists())

    def test_skipped_duty_writes_no_reservation(self):
        self.duty.update(monitoring_result="SKIPPED", backlog_claim=None)
        self.write_duty()
        with patch.object(runtime, "pulse_artifacts") as artifacts:
            runtime.pulse_reserve()
        artifacts.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_existing_reservation_for_same_run_blocks_rerun(self):
        old = {"name": "icarus-pulse-quota-2026-01-01"}
        with patch.object(runtime, "pulse_artifacts", side_effect=[[], [old]]):
            runtime.pulse_reserve()
        self.assertFalse(self.reservation.exists())

    def test_ninth_receipt_allows_a_tenth_and_consumes_it_once(self):
        with patch.object(runtime, "pulse_artifacts", side_effect=[[{}] * 9, []]):
            runtime.pulse_reserve()
        self.assertEqual(self.output.read_text(encoding="utf-8"),
                         f"day={self.day}\nissue=12\ntask_id=BACKLOG-12\ndispatch_comment_id=301\n")
        own = {"id": 201, "workflow_run": {"id": 101}, "expired": False}
        other = {"id": 200, "workflow_run": {"id": 100}, "expired": False}
        with patch.multiple(runtime, PULSE_DAY=None), patch.object(runtime, "main", return_value=0) as main:
            with patch.object(runtime, "pulse_artifacts", return_value=[other] * 9 + [own]):
                self.assertEqual(runtime.pulse_infer(), 0)
                with self.assertRaises(FileNotFoundError):
                    runtime.pulse_infer()
        main.assert_called_once_with(pulse_issue=12, pulse_execute=True, pulse_dispatch_comment_id=301)

    def test_missing_or_incomplete_receipt_blocks_inference(self):
        with patch.object(runtime, "pulse_artifacts", side_effect=[[], []]):
            runtime.pulse_reserve()
        with patch.object(runtime, "pulse_artifacts", return_value=[]), patch.object(runtime, "main") as main:
            with self.assertRaisesRegex(RuntimeError, "could not be read back"):
                runtime.pulse_infer()
        main.assert_not_called()
        with patch.object(runtime, "_api", return_value=(200, '{"total_count":1,"artifacts":[]}')):
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                runtime.pulse_reserve()

    def test_pulse_task_context_requires_exact_issue_99_dispatch_and_owner_source(self):
        dispatch = {
            "id": 301, "user": {"id": 41898282},
            "issue_url": "https://api.github.com/repos/example/Teamchat/issues/99",
            "body": "\n".join([
                "[ICARUS DISPATCH]", "Task ID: BACKLOG-12", "Target Chair: [SOL]",
                "Directive: Execute bounded task", "Source Issue: #12 (comment 300)",
                "Source File: STATUS.md", "Source Blob: " + "a" * 40,
            ]),
        }
        source = {
            "number": 12, "state": "open", "author_association": "OWNER",
            "title": "[READY] Sol worker task",
            "body": "\n".join(["[TO] [SOL]", "[SOURCE_FILE] STATUS.md",
                             "OWNER_APPROVED: update only the approved report", "VERIFY_FILE: STATUS.md"]),
        }
        content = {"sha": "a" * 40}
        with patch.object(runtime, "http", side_effect=[
            (200, json.dumps(dispatch)), (200, json.dumps(source)), (200, json.dumps(content)),
        ]) as request:
            context = runtime.pulse_task_context(12, 301)
        self.assertTrue(context["owner_approved"])
        self.assertTrue(context["has_verification_gates"])
        self.assertTrue(context["owner_authorized_branch_writes"])
        self.assertEqual(context["fields"]["task id"], "BACKLOG-12")
        self.assertEqual(request.call_count, 3)

    def test_pulse_task_context_allows_owner_sol_task_without_source_and_binds_branch_authority(self):
        dispatch = {
            "id": 302, "user": {"id": 41898282},
            "issue_url": "https://api.github.com/repos/example/Teamchat/issues/99",
            "body": chr(10).join(["[ICARUS DISPATCH]", "Task ID: BACKLOG-13", "Target Chair: [SOL]",
                                  "Directive: Diagnose backlog", "Source Issue: #13 (comment 300)"]),
        }
        source = {"number": 13, "state": "open", "author_association": "OWNER",
                  "title": "[READY] Sol diagnosis", "body": chr(10).join(["[TO] [SOL]", "Inspect the current repo and report the blocker."])}
        with patch.object(runtime, "http", side_effect=[(200, json.dumps(dispatch)), (200, json.dumps(source))]):
            context = runtime.pulse_task_context(13, 302)
        self.assertFalse(context["owner_approved"])
        self.assertFalse(context["has_verification_gates"])
        self.assertTrue(context["owner_authorized_branch_writes"])
        with patch.object(runtime, "BRANCH", "icarus/sol-pulse-123"), patch.object(runtime, "CFG", dict(runtime.CFG)):
            tools = runtime.configure_pulse_executor(context["owner_authorized_branch_writes"])
        self.assertIn("write_file", tools)

    def test_pulse_executor_exposes_only_branch_write_on_isolated_sol_branch(self):
        with patch.object(runtime, "CFG", dict(runtime.CFG)):
            with patch.object(runtime, "BRANCH", "main"):
                tools = runtime.configure_pulse_executor(True)
                self.assertNotIn("write_file", tools)
            with patch.object(runtime, "BRANCH", "icarus/sol-pulse-123"):
                tools = runtime.configure_pulse_executor(False)
                self.assertNotIn("write_file", tools)
                tools = runtime.configure_pulse_executor(True)
                self.assertIn("write_file", tools)
            self.assertNotIn("delete_file", tools)
            self.assertNotIn("delegate", tools)
            self.assertNotIn("comment_issue", tools)
            self.assertNotIn("close_issue", tools)
            self.assertEqual(runtime.CFG["maxToolCalls"], 8)
            self.assertEqual(runtime.CFG["maxWrites"], 2)
            self.assertFalse(runtime.CFG["writeBack"])

    def test_verify_file_reads_back_touched_file_from_execution_branch(self):
        with patch.object(runtime, "TOUCHED", {"README.md": "written"}), \
             patch.object(runtime, "_gh_get", return_value=(200, {"type": "file"})) as readback:
            ok, detail = runtime.gate("VERIFY_FILE: README.md")
        self.assertTrue(ok)
        self.assertIn("execution_branch=True", detail)
        readback.assert_called_once_with("README.md")

    def test_provider_failure_does_not_retry_or_fall_back(self):
        models = {runtime.PULSE_MODEL: "google", "test-fallback": "openrouter"}
        with patch.multiple(runtime, KEY="test-key", CFG=dict(runtime.CFG), STATE={"calls": 0},
                            PROVIDER=models, LOG=[], RPD={}, USAGE={}, SKIPPED=[]), \
             patch.object(runtime, "approved", return_value=(list(models), "")), \
             patch.object(runtime, "tool_read_issue", return_value="#12 [open] backlog fixture"), \
             patch.object(runtime, "http", return_value=(503, "unavailable")) as provider, \
             patch.object(runtime.time, "sleep") as sleep, redirect_stdout(io.StringIO()):
            self.assertEqual(runtime.main(pulse_issue=12), 1)
        provider.assert_called_once()
        method, url, body = provider.call_args.args
        self.assertEqual(method, "POST")
        self.assertTrue(url.endswith(f"/{runtime.PULSE_MODEL}:generateContent"))
        self.assertIn("#12 [open] backlog fixture", json.dumps(body))
        sleep.assert_not_called()
