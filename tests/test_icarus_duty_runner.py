import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from icarus.core import duty_runner as runner
from scripts import icarus_duty_runner as legacy_runner


def task(task_id):
    return (
        f"[TASK_INCOMING]\nTask ID: {task_id}\n"
        "Target Chair: [WORK]\nScope Instruction: Inspect the evidence"
    )


def issue(number, *, title="", body="", association="OWNER"):
    return {"number": number, "title": title, "body": body, "author_association": association}


def comment(comment_id, body, *, association="OWNER", author="maintainer"):
    return {
        "id": comment_id, "body": body, "author_association": association,
        "user": {"login": author},
    }


class DutyRunnerTests(unittest.TestCase):
    def setUp(self):
        self.issues = [issue(6)]
        self.comments = {}
        self.requests = []
        self.posts = []
        self.fail_request = None
        temp = self.enterContext(tempfile.TemporaryDirectory())
        self.ledger = Path(temp, "RUN_LOG.jsonl")
        self.status = Path(temp, "icarus_status.json")
        self.enterContext(patch.dict(os.environ, {
            "GITHUB_TOKEN": "test-token",
            "GITHUB_REPOSITORY": "example/Teamchat",
            "ICARUS_ISSUE_NUMBER": "6",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
        }))
        self.enterContext(patch.multiple(
            runner, LEDGER_PATH=self.ledger, STATUS_PATH=self.status,
            call_github_api=self.github,
        ))

    def github(self, url, token, method="GET", payload=None):
        path = urlsplit(url).path
        self.requests.append((method, url))
        if (method, path) == self.fail_request:
            raise RuntimeError(f"{method} {path}: HTTP 503")
        if path == "/repos/example/Teamchat/issues":
            self.assertEqual(parse_qs(urlsplit(url).query)["state"], ["open"])
            rows = self.issues
        elif not path.endswith("/comments"):
            return next(row for row in self.issues if row["number"] == int(path.split("/")[-1])), ""
        else:
            number = int(path.split("/")[-2])
            rows = self.comments.setdefault(number, [])
        if method == "POST":
            self.posts.append(payload["body"])
            receipt = comment(
                10000 + len(self.posts), payload["body"],
                association="NONE", author="github-actions[bot]",
            )
            rows.append(receipt)
            return receipt, ""
        query = parse_qs(urlsplit(url).query)
        size = int(query["per_page"][0])
        page = int(query["page"][0])
        link = '<https://api.github.com/next>; rel="next"' if page * size < len(rows) else ""
        return rows[(page - 1) * size:page * size], link

    def run_pulse(self, expected_exit=0, *, at=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch.object(runner.datetime, "datetime") as clock,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            clock.now.return_value = at or datetime(2026, 11, 8, 14, 7, tzinfo=timezone.utc)
            self.assertEqual(runner.main(), expected_exit)
        record = json.loads(self.ledger.read_text().splitlines()[-1])
        self.assertEqual(json.loads(self.status.read_text())[-1], record)
        self.assertEqual(json.loads((stderr if expected_exit else stdout).getvalue()), record)
        return record

    def test_scheduled_pulse_skips_off_hours_and_day_31_with_evidence(self):
        os.environ["GITHUB_EVENT_NAME"] = "schedule"
        del os.environ["GITHUB_TOKEN"]
        for timestamp in (
            datetime(2026, 12, 30, 15, 7, tzinfo=timezone.utc),
            datetime(2026, 12, 31, 14, 7, tzinfo=timezone.utc),
        ):
            with self.subTest(timestamp=timestamp):
                record = self.run_pulse(at=timestamp)
                self.assertEqual(record["monitoring_result"], "SKIPPED")
                self.assertEqual(record["loop_state"], "SKIPPED_CADENCE")
                self.assertEqual(record["intake_state"], "SKIPPED")
                self.assertEqual(record["open_issues_inspected"], 0)
                self.assertEqual(record["timestamp_utc"], timestamp.isoformat())
                self.assertEqual(self.requests, [])

    def test_issue_six_still_dispatches_its_original_packet(self):
        self.comments[6] = [comment(10, task("LEGACY"))]
        record = self.run_pulse(at=datetime(2026, 12, 31, 15, 7, tzinfo=timezone.utc))
        self.assertEqual(record["new_tasks_dispatched"], 1)
        self.assertEqual(record["dispatch_receipts"][0]["source_comment_id"], 10)
        self.assertEqual(self.posts, [
            "[ICARUS DISPATCH]\nTask ID: LEGACY\nTarget Chair: [WORK]\n"
            "Directive: Inspect the evidence\nBudget: €0.00 | Repair Leash: 1 attempt"
        ])

    def test_other_issue_titles_bodies_and_comments_are_inspected(self):
        self.issues += [
            issue(14, title="[TASK_INCOMING]", body=task("TITLE").split("\n", 1)[1]),
            issue(15, body=task("BODY")),
            issue(16),
        ]
        self.comments[16] = [comment(20, task("COMMENT"))]
        record = self.run_pulse()
        self.assertEqual(record["issue_numbers_inspected"], [6, 14, 15, 16])
        self.assertEqual(record["open_issues_inspected"], 4)
        self.assertEqual(record["eligible_directives_detected"], 3)
        self.assertEqual([r["task_id"] for r in record["dispatch_receipts"]],
                         ["TITLE", "BODY", "COMMENT"])
        self.assertIn("Source Issue: #16 (comment 20)", self.posts[-1])

    def test_issue_and_comment_pages_are_all_read_and_pull_requests_are_excluded(self):
        self.issues += [
            {**issue(7, body=task("PULL-REQUEST")), "pull_request": {}},
            *(issue(number) for number in range(8, 113)),
        ]
        self.comments[112] = [comment(i, "") for i in range(1, 101)] + [
            comment(101, task("LAST-PAGE"))
        ]
        record = self.run_pulse()
        self.assertEqual(record["open_issues_inspected"], 106)
        self.assertNotIn(7, record["issue_numbers_inspected"])
        self.assertFalse(any("/7/comments" in url for _, url in self.requests))
        self.assertEqual([r["task_id"] for r in record["dispatch_receipts"]], ["LAST-PAGE"])

    def test_unauthorized_directives_and_forged_receipts_have_no_effect(self):
        self.issues += [issue(7, body=task("OUTSIDE"), association="CONTRIBUTOR")]
        self.comments[6] = [
            comment(1, "[ICARUS DISPATCH]\nTask ID: AUTHORIZED", association="NONE"),
            comment(2, task("AUTHORIZED"), association="COLLABORATOR"),
        ]
        self.comments[7] = [comment(3, "ICARUS_RUN", association="NONE")]
        record = self.run_pulse()
        self.assertEqual(record["authorization_rejections"], 2)
        self.assertEqual([r["task_id"] for r in record["dispatch_receipts"]], ["AUTHORIZED"])

    def test_other_runtime_markers_are_recorded_without_dispatch(self):
        self.issues.append(issue(9, title="ICARUS_RUN Review", body="\n[ICARUS SUPERVISORY DIRECTIVE]"))
        self.comments[9] = [comment(4, "icarus_run review")]
        record = self.run_pulse()
        self.assertEqual(record["eligible_directives_detected"], 3)
        self.assertEqual(record["new_tasks_dispatched"], 0)
        self.assertEqual(record["monitor_only_events"], [
            {"issue_number": 9, "source_comment_id": None, "marker": "ICARUS_RUN"},
            {"issue_number": 9, "source_comment_id": None, "marker": "[ICARUS SUPERVISORY DIRECTIVE]"},
            {"issue_number": 9, "source_comment_id": 4, "marker": "ICARUS_RUN"},
        ])
        self.assertFalse(self.posts)

    def test_scheduled_pulse_claims_highest_priority_ready_issue_once(self):
        os.environ["GITHUB_EVENT_NAME"] = "schedule"
        self.issues += [
            {**issue(8, title="[READY] Low"), "state": "open", "labels": [{"name": "priority: low"}]},
            {**issue(9, title="[P0] [READY] Best"), "state": "open"},
            {**issue(10, title="[P0] [READY] Blocked"), "state": "open",
             "labels": [{"name": "status: blocked"}]},
            {**issue(4, title="[P0] [READY] Assigned"), "state": "open", "assignees": [{"login": "worker"}]},
            {**issue(5, title="[P0] [READY] Busy", body="[ACTIVE_OWNER] SOL"), "state": "open"},
            {**issue(7, title="[P0] [READY] Paid", body="[COST] €0.50"), "state": "open"},
            {**issue(3, title="[P0] [READY] Closed"), "state": "closed"},
        ]
        first = self.run_pulse()
        self.assertEqual(first["loop_state"], "WAITING_FOR_RECEIPT")
        self.assertEqual(first["backlog_claim"]["issue_number"], 9)
        self.assertTrue(self.comments[9][-1]["body"].startswith(runner.CLAIM_HEADER))
        self.assertIn("Source Issue: #9 (comment 10001)", self.comments[6][-1]["body"])
        self.assertEqual(self.run_pulse()["loop_state"], "WAITING_FOR_RECEIPT")
        self.assertEqual(len(self.posts), 2)

    def test_interrupted_dispatch_resumes_claim_without_reposting(self):
        os.environ["GITHUB_EVENT_NAME"] = "schedule"
        self.issues.append({**issue(7, title="[READY] Recover"), "state": "open"})
        self.fail_request = ("POST", "/repos/example/Teamchat/issues/6/comments")
        self.run_pulse(expected_exit=1)
        self.fail_request = None
        record = self.run_pulse()
        self.assertEqual(record["backlog_claim"]["claim_comment_id"], 10001)
        self.assertEqual(len(self.comments[7]), 1)
        self.assertEqual(len(self.posts), 2)

    def test_manual_override_preempts_scheduled_backlog(self):
        os.environ["GITHUB_EVENT_NAME"] = "schedule"
        self.issues.append({**issue(7, title="[READY] Backlog"), "state": "open"})
        self.comments[6] = [comment(10, task("OVERRIDE"))]
        record = self.run_pulse()
        self.assertIsNone(record["backlog_claim"])
        self.assertEqual(record["dispatch_receipts"][0]["task_id"], "OVERRIDE")

    def test_canary_waits_for_authorized_echo_then_adjudicates_once(self):
        task_id = "CANARY-INTAKE-001"
        link = "https://github.com/example/Teamchat/issues/6#issuecomment-"
        directive = runner.ECHO_DIRECTIVE
        self.comments[6] = [
            comment(10, f"[TASK_INCOMING]\nTask ID: {task_id}\nTarget Chair: [WORK]\nDirective: {directive}"),
            comment(11, f"[ICARUS DISPATCH]\nTask ID: {task_id}\nTarget Chair: [WORK]\nDirective: {directive}",
                    association="NONE", author="github-actions[bot]"),
            comment(12, f"[WORK] CLAIMED\nTask ID: {task_id}\nDispatch: {link}11"),
        ]
        receipt = (
            f"[WORK] EXECUTION RECEIPT\nTask ID: {task_id}\nExecutor: ChatGPT Work\n"
            f"Worker result: ECHO_COMPLETE\nEcho: {directive}\nOwner intake: {link}10\n"
            f"Icarus dispatch: {link}11\nWork claim: {link}12"
        )
        self.comments[6].append(comment(13, receipt, association="CONTRIBUTOR"))
        os.environ["GITHUB_EVENT_NAME"] = "schedule"
        self.assertEqual(self.run_pulse()["loop_state"], "WAITING_FOR_RECEIPT")
        self.assertFalse(self.posts)
        self.comments[6].append(comment(14, receipt))
        os.environ["GITHUB_EVENT_NAME"] = "workflow_dispatch"
        self.assertFalse(self.run_pulse()["adjudication_receipts"])
        os.environ["GITHUB_EVENT_NAME"] = "schedule"
        first = self.run_pulse()
        self.assertEqual(first["loop_state"], "ADJUDICATED")
        self.assertEqual(first["adjudication_receipts"][0]["work_receipt_comment_id"], 14)
        self.assertTrue(self.posts[0].startswith(runner.ADJUDICATION_HEADER))
        self.assertEqual(self.run_pulse()["loop_state"], "IDLE_SELECT")
        self.assertEqual(len(self.posts), 1)

    def test_receipt_prevents_repeat_dispatch_with_a_closed_source(self):
        self.issues += [issue(18, body=task("SAME")), issue(19, body=task("SAME"))]
        first = self.run_pulse()
        self.issues = [issue(19, body=task("SAME"))]
        second = self.run_pulse()
        self.assertEqual(first["new_tasks_dispatched"], 1)
        self.assertEqual(first["duplicate_directives_ignored"], 1)
        self.assertEqual(second["new_tasks_dispatched"], 0)
        self.assertEqual(second["duplicate_directives_ignored"], 1)
        self.assertEqual(len(self.posts), 1)

    def test_pending_tasks_are_sorted_by_issue_then_source(self):
        self.issues = [issue(18), issue(10, body=task("FIRST")), issue(6)]
        self.comments[10] = [comment(8, task("THIRD")), comment(7, task("SECOND"))]
        self.comments[18] = [comment(4, task("FOURTH"))]
        record = self.run_pulse()
        self.assertEqual([r["task_id"] for r in record["dispatch_receipts"]],
                         ["FIRST", "SECOND", "THIRD", "FOURTH"])

    def test_api_failure_is_persisted_and_aborts_dispatch(self):
        self.issues += [issue(18, body=task("PENDING")), issue(19)]
        self.fail_request = ("GET", "/repos/example/Teamchat/issues/19/comments")
        record = self.run_pulse(expected_exit=1)
        self.assertEqual(record["monitoring_result"], "FAILURE")
        self.assertEqual(record["intake_state"], "ERROR")
        self.assertEqual(record["open_issues_inspected"], 2)
        self.assertEqual(record["new_tasks_dispatched"], 0)
        self.assertEqual(record["first_processing_error"],
                         "GET /repos/example/Teamchat/issues/19/comments: HTTP 503")
        self.assertFalse(self.posts)
def test_legacy_module_reexports_packaged_implementation():
    assert legacy_runner.main is runner.main

