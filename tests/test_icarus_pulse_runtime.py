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
    def test_duplicate_detection_does_not_conflate_issue_137_with_issue_218(self):
        rows = [{
            "number": 137, "state": "open",
            "title": "[T1] [REQUESTED] Enforce true adjudication and physical evidence readback",
            "body": "[OBJECTIVE] Enforce true adjudication and physical evidence readback for open issue #6.",
            "html_url": "https://github.com/example/Teamchat/issues/137",
        }]
        objective = "Execute existing open Teamchat task #218 exactly within its declared scope (Sol review and delegation only)."
        with patch.object(runtime, "http", return_value=(200, json.dumps(rows))):
            self.assertEqual(runtime._open_task_dup(objective), "")

    def test_duplicate_detection_blocks_same_objective_and_same_issue_scope(self):
        objective = "Implement smallest decision/delegation fix for issue #272"
        rows = [{
            "number": 280, "state": "open",
            "title": "[T1] [REQUESTED] Implement smallest decision/delegation fix",
            "body": f"[OBJECTIVE] {objective}",
            "html_url": "https://github.com/example/Teamchat/issues/280",
        }]
        with patch.object(runtime, "http", return_value=(200, json.dumps(rows))):
            self.assertIn("#280", runtime._open_task_dup(objective))

    def test_any_executor_is_an_explicit_generic_delegate_target(self):
        selected, reason = runtime._select_delegate_target(
            "ANY", "Implement the runtime executor routing fix", {"SOL"}, runtime.CFG["delegateTargets"],
        )
        self.assertEqual(selected, "ANY")
        self.assertIn("available eligible executor", reason)
        self.assertIn("ANY AVAILABLE EXECUTOR", runtime.rules_text())

    def test_sol_bench_routes_code_work_to_claude_and_blocks_other_sol_work(self):
        targets = runtime.CFG["delegateTargets"]
        selected, reason = runtime._select_delegate_target(
            "SOL", "Implement the runtime decision fix", {"SOL"}, targets,
        )
        self.assertEqual(selected, "CLAUDE")
        self.assertIn("Claude", reason)
        selected, reason = runtime._select_delegate_target(
            "SOL", "Implement the runtime decision fix", {"SOL", "CLAUDE"}, targets,
        )
        self.assertEqual(selected, "CODEX")
        self.assertIn("Codex", reason)
        selected, reason = runtime._select_delegate_target(
            "SOL", "Review the open task and report status", {"SOL"}, targets,
        )
        self.assertEqual(selected, "")
        self.assertIn("benched", reason)

    def test_loop_off_restricts_owner_command_to_read_only_tools(self):
        cfg = dict(runtime.CFG)
        cfg.update({
            "tools": ["read_file", "read_issue", "list_issues", "write_file", "delegate", "comment_issue", "close_issue"],
            "maxToolCalls": 2, "maxApiCallsPerRun": 12, "dailyRunCap": 10,
            "maxRuntimeSeconds": 120, "writeBack": False,
        })
        answer = {"answer": "READ_ONLY_PATH_REACHED", "tool": None,
                  "unverified_claims": [], "needs_owner": False, "owner_reason": "", "lesson": ""}
        with patch.multiple(
            runtime,
            RAW="ICARUS_RUN LOOP: off\nRead issue #259 and report its adjudication marker. Do not write or delegate.",
            KEY="test-key", GH_TOKEN="", REPO="", CID="77", ACTOR="owner", CFG=cfg,
            PROVIDER={"test-model": "google"}, USAGE={}, LOG=[], SKIPPED=[], RECALLED=[],
            BLOCKER_RECALLS={"n": 0}, DELEGATED=[], DELEG_KEYS={}, LOOP_ON={"v": False},
        ), patch.object(runtime, "approved", return_value=(["test-model"], "")), \
             patch.object(runtime, "usage_today", return_value={}), \
             patch.object(runtime, "thread_context", return_value=(0, "")), \
             patch.object(runtime, "run_step", return_value=(answer, "test-model", "", False)) as step, \
             redirect_stdout(io.StringIO()):
            runtime.main()

        self.assertEqual(step.call_count, 1)
        self.assertEqual(step.call_args.args[7], runtime.LOOP_READ)
        self.assertFalse({"write_file", "delete_file", "delegate", "comment_issue", "close_issue"}
                         & step.call_args.args[7])
        self.assertFalse(runtime.LOOP_ON["v"])


    def test_legacy_runtime_module_reexports_packaged_implementation(self):
        self.assertIs(legacy_runtime.main, runtime.main)

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
            "dispatch_receipts": [{"issue_number": 12, "task_id": "BACKLOG-12"}],
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
        self.assertEqual(self.output.read_text(encoding="utf-8"), f"day={self.day}\n")
        own = {"id": 201, "workflow_run": {"id": 101}, "expired": False}
        other = {"id": 200, "workflow_run": {"id": 100}, "expired": False}
        with patch.multiple(runtime, PULSE_DAY=None), patch.object(runtime, "main", return_value=0) as main:
            with patch.object(runtime, "pulse_artifacts", return_value=[other] * 9 + [own]):
                self.assertEqual(runtime.pulse_infer(), 0)
                with self.assertRaises(FileNotFoundError):
                    runtime.pulse_infer()
        main.assert_called_once_with(pulse_issue=12)

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
