import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from scripts import icarus_duty_runner as runner


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
        else:
            number = int(path.split("/")[-2])
            rows = self.comments.setdefault(number, [])
        if method == "POST":
            self.assertEqual(number, 6)
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

    def run_pulse(self, expected_exit=0):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(runner.main(), expected_exit)
        record = json.loads(self.ledger.read_text().splitlines()[-1])
        self.assertEqual(json.loads(self.status.read_text())[-1], record)
        self.assertEqual(json.loads((stderr if expected_exit else stdout).getvalue()), record)
        return record

    def test_issue_six_still_dispatches_its_original_packet(self):
        self.comments[6] = [comment(10, task("LEGACY"))]
        record = self.run_pulse()
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
