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


    def run_loop(self, decide_text, act_events=(), tool_results=(), raw=None):
        """Run one owner ICARUS_RUN loop with scripted step answers; return the receipt text."""
        Path("STATUS.md").write_text("status", encoding="utf-8")
        cfg = dict(runtime.CFG)
        cfg.update({"tools": ["read_file", "list_issues", "write_file", "delegate", "comment_issue", "close_issue"],
                    "maxToolCalls": 4, "maxApiCallsPerRun": 12, "dailyRunCap": 10,
                    "maxRuntimeSeconds": 120, "writeBack": False})
        texts = ["discovered the board", decide_text, "acted"]

        def step(*args, **kwargs):
            n = runtime.CUR_STEP["n"]
            if n == 3:
                runtime.ACT_EVENTS.extend(act_events)
                runtime.TOOL_RESULTS.extend(tool_results)
            return ({"answer": texts[n - 1], "tool": None, "unverified_claims": [],
                     "needs_owner": False, "owner_reason": "", "lesson": ""}, "test-model", "", False)
        with patch.multiple(
            runtime, RAW=raw or "ICARUS_RUN Review the board and act.\nVERIFY_FILE: STATUS.md",
            KEY="test-key", CID="88", ACTOR="owner", CFG=cfg,
            PROVIDER={"test-model": "google"}, USAGE={}, LOG=[], SKIPPED=[], RECALLED=[],
            BLOCKER_RECALLS={"n": 0}, DELEGATED=[], DELEG_KEYS={}, LOOP_ON={"v": False},
        ), patch.object(runtime, "approved", return_value=(["test-model"], "")), \
             patch.object(runtime, "usage_today", return_value={}), \
             patch.object(runtime, "thread_context", return_value=(0, "")), \
             patch.object(runtime, "http", return_value=(404, "")), \
             patch.object(runtime, "run_step", side_effect=step), redirect_stdout(io.StringIO()):
            self.last_rc = runtime.main()
        return next(Path("icarus/runs").glob("*-88.md")).read_text(encoding="utf-8")

    def test_delegate_decision_without_a_delegate_call_fails(self):
        receipt = self.run_loop("Delegating up to 10 issues.\nDECISION: DELEGATE")
        self.assertIn("VERDICT: FAIL - execution failed: ACT_STEP_NO_ACTION: decision=DELEGATE", receipt)
        self.assertIn("decision: DELEGATE", receipt)

    def test_fail_verdict_returns_nonzero_and_pass_returns_zero(self):
        self.run_loop("DECISION: DO_MYSELF", act_events=[(3, "write_file", False)])
        self.assertEqual(self.last_rc, 1)
        self.run_loop("DECISION: DELEGATE", act_events=[(3, "delegate", True)])
        self.assertEqual(self.last_rc, 0)

    def test_missing_verification_gate_is_fail_and_nonzero(self):
        receipt = self.run_loop("DECISION: DELEGATE", act_events=[(3, "delegate", True)], raw="ICARUS_RUN Review the board and act.")
        self.assertIn("VERDICT: FAIL - no evidence gate supplied", receipt)
        self.assertEqual(self.last_rc, 1)

    def test_tool_results_do_not_leak_into_the_next_run(self):
        self.run_loop("DECISION: DO_MYSELF", act_events=[(3, "comment_issue", False)],
                      tool_results=["[step 3] comment_issue: COMMENT FAILED: HTTP 403"])
        receipt = self.run_loop("DECISION: DELEGATE", act_events=[(3, "delegate", True)])
        self.assertNotIn("Tool results", receipt)
        self.assertNotIn("HTTP 403", receipt)

    def test_receipt_records_the_failed_tool_result(self):
        receipt = self.run_loop("DECISION: DO_MYSELF", act_events=[(3, "comment_issue", False)],
                                tool_results=["[step 3] comment_issue: COMMENT FAILED: HTTP 403 Resource not accessible"])
        self.assertIn("- Tool results (redacted, 200 chars each): [step 3] comment_issue: COMMENT FAILED: HTTP 403", receipt)
        self.assertIn("VERDICT: FAIL", receipt)

    def test_redact_result_masks_common_secret_shapes(self):
        gh, pat, aiza, orv1 = "ghp_" + "a" * 36, "github_pat_" + "B" * 30, "AIza" + "c" * 35, "sk-or-v1-" + "d" * 30
        env_secret = "envsecretvalue123"
        raw = (f"HTTP 401 Bad credentials: Authorization: Bearer {gh} / {pat} / key={aiza} / {orv1} / "
               f'{{"token": "plainvalue99"}} / {env_secret}')
        with patch.object(runtime, "GH_TOKEN", env_secret):
            out = runtime.redact_result(raw)
        for leaked in (gh, pat, aiza, orv1, "plainvalue99", env_secret):
            self.assertNotIn(leaked, out)
        self.assertIn("HTTP 401 Bad credentials", out)

    def test_redact_result_edge_cases(self):
        gh = "ghp_" + "a" * 36
        cases = [
            f"BEARER {gh}.", f"bearer\n{gh}", f"token:\n  abcdef123456", f'"token":"abcdef123456"', "token=abcdef123456;",
            "Authorization: Basic dXNlcjpwYXNzd29yZA==", f"GHP_{'A' * 36}", f"x-api-key: {'k' * 20}",
        ]
        for raw in cases:
            out = runtime.redact_result(raw)
            self.assertIn("[REDACTED]", out, raw)
            for frag in ("abcdef123456", "dXNlcjpwYXNzd29yZA", "a" * 20, "A" * 20, "k" * 20):
                self.assertNotIn(frag, out, raw)
        for benign in ("HTTP 404 not found", "ghp_short", "", None, {"a": 1}, 403):
            runtime.redact_result(benign)
        self.assertEqual(runtime.redact_result("HTTP 404 not found"), "HTTP 404 not found")

    def test_redact_result_masks_whole_quoted_values(self):
        cases = [
            ('{"password": "first-part second-part"}', "second-part"),
            ('{"token": "abc def ghi jkl"}', "def ghi"),
            ('{"password": "pa\\"ss word tail"}', "word tail"),
            ('{"secret": "line1\nline2 tail"}', "line2 tail"),
            ("{'password': 'single quoted secret words'}", "secret words"),
            ('{"client_secret": "csval123456 more"}', "csval123456"),
            ('{"refresh_token": "rtval123456"}', "rtval123456"),
            ("refresh_token=rtval123456", "rtval123456"),
            ('{"password": "unterminated value with spaces', "value with spaces"),
        ]
        for raw, leaked in cases:
            out = runtime.redact_result(raw)
            self.assertNotIn(leaked, out, raw)
            self.assertIn("[REDACTED]", out, raw)
        self.assertEqual(runtime.redact_result('{"message": "Resource not accessible by integration", "status": "403"}'),
                         '{"message": "Resource not accessible by integration", "status": "403"}')

    def test_run_step_redacts_a_secret_that_straddles_the_truncation_point(self):
        gh = "ghp_" + "a" * 36
        cfg = dict(runtime.CFG)
        cfg.update({"tools": ["comment_issue"], "maxToolCalls": 3})
        replies = iter([({"tool": {"name": "comment_issue", "args": {}}}, "m", "", False), ({"answer": "done", "tool": None}, "m", "", False)])
        runtime.TOOL_RESULTS.clear()
        with patch.multiple(runtime, CFG=cfg, CUR_STEP={"n": 3}, BLOCKER_RECALLS={"n": 2}), \
             patch.dict(runtime.TOOLS, {"comment_issue": lambda a: "y" * 170 + " token=" + gh}), \
             patch.object(runtime, "pool", side_effect=lambda *a, **k: next(replies)):
            runtime.run_step("sys", "step", "", [], None, None, [], None)
        runtime.ACT_EVENTS.clear()
        self.assertNotIn("ghp_", runtime.TOOL_RESULTS[0])
        self.assertNotIn("aaaa", runtime.TOOL_RESULTS[0])
        runtime.TOOL_RESULTS.clear()

    def test_run_step_stores_a_redacted_truncated_tool_result(self):
        cfg = dict(runtime.CFG)
        cfg.update({"tools": ["comment_issue"], "maxToolCalls": 3})
        replies = iter([({"tool": {"name": "comment_issue", "args": {"number": 259, "body": "x"}}}, "m", "", False),
                        ({"answer": "done", "tool": None}, "m", "", False)])
        runtime.TOOL_RESULTS.clear()
        with patch.multiple(runtime, CFG=cfg, CUR_STEP={"n": 3}, BLOCKER_RECALLS={"n": 2}), \
             patch.dict(runtime.TOOLS, {"comment_issue": lambda a: "COMMENT FAILED: HTTP 403\n" + "x" * 500}), \
             patch.object(runtime, "pool", side_effect=lambda *a, **k: next(replies)):
            runtime.run_step("sys", "step", "", [], None, None, [], None)
        runtime.ACT_EVENTS.clear()
        self.assertEqual(len(runtime.TOOL_RESULTS), 1)
        self.assertTrue(runtime.TOOL_RESULTS[0].startswith("[step 3] comment_issue: COMMENT FAILED: HTTP 403 xxx"))
        self.assertLessEqual(len(runtime.TOOL_RESULTS[0]), len("[step 3] comment_issue: ") + 200)
        runtime.TOOL_RESULTS.clear()

    def test_delegate_decision_with_a_read_back_delegation_passes(self):
        receipt = self.run_loop("DECISION: DELEGATE", act_events=[(3, "delegate", True)])
        self.assertIn("VERDICT: PASS - all gates passed", receipt)

    def test_do_myself_needs_a_successful_mutation_in_the_act_step(self):
        receipt = self.run_loop("DECISION: DO_MYSELF", act_events=[(3, "write_file", False)])
        self.assertIn("ACT_STEP_NO_ACTION: decision=DO_MYSELF", receipt)
        self.assertIn("VERDICT: FAIL", receipt)

    def test_decide_step_without_a_structured_decision_fails(self):
        receipt = self.run_loop("I reviewed everything and it is all covered.")
        self.assertIn("DECIDE_STEP_NO_STRUCTURED_DECISION", receipt)
        self.assertIn("VERDICT: FAIL", receipt)

    def test_tool_success_reads_only_real_read_back_results(self):
        self.assertTrue(runtime._tool_succeeded("delegate", "DELEGATED (status REQUESTED, NOT executed): task #5 u -> CLAUDE; readback OK"))
        self.assertFalse(runtime._tool_succeeded("delegate", "ALREADY DELEGATED: open task #5 covers this"))
        self.assertFalse(runtime._tool_succeeded("write_file", "WRITE FAILED: HTTP 409 protected branch"))
        self.assertFalse(runtime._tool_succeeded("comment_issue", "COMMENTED on #5: u; readback FAILED"))

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
        main.assert_called_once_with(pulse_issue=12, self_task=False)

    def test_self_task_outranks_triage_and_runs_in_self_mode(self):
        self.duty["self_task"] = {"issue_number": 44, "task_id": "BACKLOG-44", "reason": "held: no available agent"}
        self.write_duty()
        with patch.object(runtime, "pulse_artifacts", side_effect=[[], []]):
            runtime.pulse_reserve()
        self.assertEqual(json.loads(self.reservation.read_text(encoding="utf-8"))["mode"], "self")
        own = {"id": 201, "workflow_run": {"id": 101}, "expired": False}
        with patch.multiple(runtime, PULSE_DAY=None), patch.object(runtime, "main", return_value=0) as main:
            with patch.object(runtime, "pulse_artifacts", return_value=[own]):
                runtime.pulse_infer()
        main.assert_called_once_with(pulse_issue=44, self_task=True)

    def run_self(self, posted):
        cfg = dict(runtime.CFG)

        def step(*args, **kwargs):
            runtime.COMMENTS_POSTED.extend(posted)
            return ({"answer": "done", "tool": None, "unverified_claims": [], "needs_owner": False,
                     "owner_reason": "", "lesson": ""}, runtime.PULSE_MODEL, "", False)
        with patch.multiple(runtime, KEY="k", CID="pulse-9", ACTOR="schedule", CFG=cfg, RAW="",
                            PROVIDER={runtime.PULSE_MODEL: "google"}, USAGE={}, LOG=[], SKIPPED=[], RECALLED=[],
                            BLOCKER_RECALLS={"n": 0}, DELEGATED=[], DELEG_KEYS={}, LOOP_ON={"v": False}), \
             patch.object(runtime, "approved", return_value=([runtime.PULSE_MODEL], "")), \
             patch.object(runtime, "usage_today", return_value={}), \
             patch.object(runtime, "tool_read_issue", return_value="#44 [open] task"), \
             patch.object(runtime, "http", return_value=(404, "")), \
             patch.object(runtime, "run_step", side_effect=step) as run, redirect_stdout(io.StringIO()):
            runtime.main(pulse_issue=44, self_task=True)
            tools = set(cfg["tools"])
        return next(Path("icarus/runs").glob("*-pulse-9.md")).read_text(encoding="utf-8"), tools, run

    def test_self_task_run_has_read_and_comment_tools_only_and_passes_on_result(self):
        receipt, tools, run = self.run_self([(44, "TAKEOVER RESULT: analysis with evidence")])
        self.assertEqual(tools, set(runtime.SELF_TOOLS))
        self.assertFalse({"write_file", "delete_file", "delegate", "close_issue"} & tools)
        self.assertIn("Take over task #44 yourself", run.call_args.args[1])
        self.assertIn("VERDICT: PASS", receipt)

    def test_self_task_blocked_comment_is_not_a_pass(self):
        receipt, _, _ = self.run_self([(44, "TAKEOVER BLOCKED: needs store access")])
        self.assertIn("VERDICT: FAIL", receipt)

    def test_self_takeover_passes_only_on_a_read_back_result_comment(self):
        with patch.object(runtime, "COMMENTS_POSTED", [(44, "TAKEOVER BLOCKED: needs store access")]):
            self.assertFalse(runtime.self_takeover_gate(44)[0])
        with patch.object(runtime, "COMMENTS_POSTED", [(45, "TAKEOVER RESULT: done")]):
            self.assertFalse(runtime.self_takeover_gate(44)[0])
        with patch.object(runtime, "COMMENTS_POSTED", [(44, "TAKEOVER RESULT: findings with evidence")]):
            self.assertTrue(runtime.self_takeover_gate(44)[0])

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
