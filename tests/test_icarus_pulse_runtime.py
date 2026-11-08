import io
import json
import os
import tempfile
import unittest
from contextlib import chdir, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from icarus.runtime import icarus_run as runtime


class PulseRuntimeTests(unittest.TestCase):
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
