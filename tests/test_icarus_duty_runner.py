import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from icarus.core import duty_runner as runner
from icarus.core import pilot_state
from scripts import icarus_duty_runner as legacy_runner


DUTY_SCHEDULE = "7 0-22/2 1-30 * *"


def task(task_id, source="harness-runner.py"):
    return (
        f"[TASK_INCOMING]\nTask ID: {task_id}\n"
        "Target Chair: [WORK]\nScope Instruction: Inspect the evidence"
        + (f"\nSource File: {source}" if source is not None else "")
    )


def issue(number, *, title="", body="", association="OWNER"):
    if "[READY]" in title and "[SOURCE_FILE]" not in body:
        body += "\n[SOURCE_FILE] harness-runner.py"
    return {"number": number, "title": title, "body": body, "author_association": association}


def comment(comment_id, body, *, association="OWNER", author="maintainer"):
    return {
        "id": comment_id, "body": body, "author_association": association,
        "user": {"login": author},
    }


def canary_comments(task_id):
    return [
        comment(10, f"[TASK_INCOMING]\nTask ID: {task_id}\nTarget Chair: [WORK]\n"
                    f"Directive: {runner.ECHO_DIRECTIVE}"),
        comment(11, f"[ICARUS DISPATCH]\nTask ID: {task_id}\nTarget Chair: [WORK]\n"
                    f"Directive: {runner.ECHO_DIRECTIVE}",
                association="NONE", author="github-actions[bot]"),
        comment(12, f"[WORK] CLAIMED\nTask ID: {task_id}\n"
                    "Dispatch: https://github.com/example/Teamchat/issues/6#issuecomment-11"),
    ]


class DutyRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo = Path(cls.enterClassContext(tempfile.TemporaryDirectory()))
        (repo / "harness-runner.py").write_text("# Source file for preflight\n", encoding="utf-8")
        (repo / "icarus").mkdir()
        (repo / "icarus" / "__init__.py").touch()
        for args in (
            ["init", "--quiet"], ["add", "."],
            ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
             "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Preflight source fixture"],
        ):
            subprocess.run(["git", *args], cwd=repo, check=True)
        cls.repo = repo

    def setUp(self):
        self.issues = [issue(6)]
        self.comments = {}
        self.requests = []
        self.posts = []
        self.fail_request = None
        self.ambiguous_patch = False
        temp = self.enterContext(tempfile.TemporaryDirectory())
        self.ledger = Path(temp, "RUN_LOG.jsonl")
        self.status = Path(temp, "icarus_status.json")
        self.enterContext(patch.dict(os.environ, {
            "GITHUB_TOKEN": "test-token",
            "GITHUB_REPOSITORY": "example/Teamchat",
            "ICARUS_ISSUE_NUMBER": "6",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "ICARUS_PULSE_DUTY_SCHEDULE": DUTY_SCHEDULE,
            "ICARUS_PULSE_TRIGGER_SCHEDULE": DUTY_SCHEDULE,
            "ICARUS_DUTY_VERIFIER_USER_ID": "",
            "ICARUS_DUTY_AGENT_SIGNERS": "",
        }))
        self.enterContext(patch.multiple(
            runner, LEDGER_PATH=self.ledger, STATUS_PATH=self.status,
            call_github_api=self.github, REPO_ROOT=self.repo,
        ))
        self.enterContext(patch.object(pilot_state, "PROOF_PATH", str(self.ledger.parent / "proof.bin")))

    def github(self, url, token, method="GET", payload=None):
        path = urlsplit(url).path
        self.requests.append((method, url))
        if (method, path) == self.fail_request:
            raise RuntimeError(f"{method} {path}: HTTP 503")
        if path == "/repos/example/Teamchat/issues":
            self.assertEqual(parse_qs(urlsplit(url).query)["state"], ["open"])
            rows = [row for row in self.issues if row.get("state") != "closed"]
        elif path.startswith("/repos/example/Teamchat/issues/comments/"):
            comment_id = int(path.rsplit("/", 1)[-1])
            return next(row for rows in self.comments.values() for row in rows if row["id"] == comment_id), ""
        elif not path.endswith("/comments"):
            row = next(row for row in self.issues if row["number"] == int(path.split("/")[-1]))
            if method == "PATCH":
                row.update(payload)
                if self.ambiguous_patch:
                    self.ambiguous_patch = False
                    raise RuntimeError("PATCH response lost after mutation")
            return row, ""
        else:
            number = int(path.split("/")[-2])
            rows = self.comments.setdefault(number, [])
        if method == "POST":
            self.posts.append(payload["body"])
            receipt = comment(
                10000 + len(self.posts), payload["body"],
                association="NONE", author="github-actions[bot]",
            )
            receipt["user"]["id"] = pilot_state.PULSE_ACTOR_ID
            receipt["issue_url"] = f"https://api.github.com{path.removesuffix('/comments')}"
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
            patch.object(runner, "datetime") as clock,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            clock.timezone = timezone
            clock.datetime.now.return_value = at or datetime(2026, 11, 8, 14, 7, tzinfo=timezone.utc)
            self.assertEqual(runner.main(), expected_exit)
        record = json.loads(self.ledger.read_text().splitlines()[-1])
        self.assertEqual(json.loads(self.status.read_text())[-1], record)
        self.assertEqual(json.loads((stderr if expected_exit else stdout).getvalue()), record)
        return record

    def test_heartbeat_and_missing_trigger_skip_duty_with_evidence(self):
        os.environ["GITHUB_EVENT_NAME"] = "schedule"
        del os.environ["GITHUB_TOKEN"]
        for trigger in ("7 1-23/2 1-30 * *", "7 * 31 * *", ""):
            with self.subTest(trigger=trigger):
                os.environ["ICARUS_PULSE_TRIGGER_SCHEDULE"] = trigger
                timestamp = datetime(2027, 1, 1, 0, 7, tzinfo=timezone.utc)
                record = self.run_pulse(at=timestamp)
                self.assertEqual(record["monitoring_result"], "SKIPPED")
                self.assertEqual(record["loop_state"], "SKIPPED_CADENCE")
                self.assertEqual(record["intake_state"], "SKIPPED")
                self.assertEqual(record["open_issues_inspected"], 0)
                self.assertEqual(record["timestamp_utc"], timestamp.isoformat())
                self.assertEqual(self.requests, [])

    def test_completed_inspection_writes_zero_task_tool_idle_receipt(self):
        os.environ["GITHUB_EVENT_NAME"] = "schedule"
        record = self.run_pulse()
        self.assertEqual(record["idle_receipt"], {
            "verdict": "PASS", "reason": "NO_TASK_ACTION_REQUIRED",
            "required_task_tool_calls": 0, "exit_code": 0,
        })
        self.assertEqual(record["issue_numbers_inspected"], [6])
        self.assertEqual(self.posts, [])

    def test_blocked_source_preflight_does_not_emit_an_idle_pass(self):
        self.comments[6] = [comment(10, task("BLOCKED", source="missing.py"))]
        record = self.run_pulse()
        self.assertEqual(record["task_states"]["BLOCKED"]["status"], "PREFLIGHT_BLOCKED")
        self.assertNotIn("idle_receipt", record)

    def terminal_proof(self, number, dispatch, *, exit_code=0, observed="a" * 64,
                       worker_id=101, verifier_id=102, source_sha="c" * 40):
        task_id = f"BACKLOG-{number}"
        worker_comment_id = dispatch + 100
        proof_comment_id = dispatch + 101
        stamps = dict(created_at="2026-11-10T14:00:00Z", updated_at="2026-11-10T14:00:00Z")
        binding = f"Task ID: {task_id}\nDispatch Comment ID: {dispatch}\nGit Commit SHA: {source_sha}"
        worker = comment(worker_comment_id, f"{runner.EXECUTION_HEADER}\n{binding}\nTarget Chair: [WORK]")
        worker.update(stamps, user={"id": worker_id, "type": "Bot", "login": "worker[bot]"})
        proof = comment(proof_comment_id, (
            f"{runner.VERIFICATION_HEADER}\n{binding}\nExecution Comment ID: {worker_comment_id}\n"
            f"Exit Code: {exit_code}\nExpected SHA256: {'a' * 64}\nObserved SHA256: {observed}\n"
            "Scope Verified: true\nIncremental Spend EUR: 0"
        ))
        proof.update(stamps, user={"id": verifier_id, "type": "Bot", "login": "verifier[bot]"})
        self.comments[6].extend([worker, proof])

    def start_backlog(self):
        os.environ["GITHUB_EVENT_NAME"] = "schedule"
        os.environ["ICARUS_DUTY_VERIFIER_USER_ID"] = "102"
        self.issues.append({**issue(9, title="[READY] Verify artifact"), "state": "open"})
        row = self.run_pulse()
        return row["dispatch_receipts"][0]["dispatch_comment_id"]

    def test_terminal_reissue_and_close_are_read_back_and_replay_safe(self):
        original = self.start_backlog()
        self.terminal_proof(9, original, observed="b" * 64)
        failed = self.run_pulse()["terminal_receipts"][0]
        retry = failed["reissue_comment_id"]
        self.assertEqual((failed["verdict"], failed["status"]), ("FAIL", "WAITING_FOR_RECEIPT"))
        self.assertEqual(self.issues[-1]["state"], "open")
        self.assertIn(f"Reissue Of: {original}", self.posts[-1])
        self.assertIn(f"independently verify expected artifact digest {'a' * 64}", self.posts[-1])
        self.assertIn("Repair Leash: 0 attempts", self.posts[-1])
        self.assertEqual(self.run_pulse()["waiting_backlog"], [
            {"task_id": "BACKLOG-9", "dispatch_comment_id": retry},
        ])

        self.terminal_proof(9, retry)
        closed = self.run_pulse()["terminal_receipts"][0]
        self.assertEqual((closed["verdict"], closed["status"], closed["exit_code"]), ("PASS", "CLOSED", 0))
        self.assertEqual(self.issues[-1]["state_reason"], "completed")
        self.assertTrue(closed["closure_comment_id"])
        count = len(self.posts)
        self.assertEqual(self.run_pulse()["terminal_receipts"], [])
        self.assertEqual(len(self.posts), count)
        self.assertEqual(sum(method == "PATCH" for method, _ in self.requests), 1)

    def test_terminal_verifier_cannot_be_the_executor(self):
        dispatch = self.start_backlog()
        self.terminal_proof(9, dispatch, worker_id=102)
        row = self.run_pulse()
        self.assertEqual(row["terminal_receipts"], [])
        self.assertNotIn("idle_receipt", row)
        self.assertEqual(self.issues[-1]["state"], "open")

    def test_same_github_account_requires_two_distinct_task_bound_signatures(self):
        dispatch = self.start_backlog()
        self.terminal_proof(9, dispatch, worker_id=102)
        worker, verifier = self.comments[6][-2:]
        for receipt in (worker, verifier):
            receipt["user"] = {"id": 102, "type": "User", "login": "maintainer"}
        outbox = "https://api.github.com/repos/example/Teamchat/issues/6/comments"
        directory = self.ledger.parent

        keys = {}
        for role in ("executor", "verifier"):
            private = directory / f"{role}.pem"
            subprocess.run(
                ["openssl", "genpkey", "-algorithm", "ED25519", "-out", str(private)], check=True,
            )
            der = subprocess.check_output([
                "openssl", "pkey", "-in", str(private), "-pubout", "-outform", "DER",
            ])
            self.assertEqual(der[:-32].hex(), "302a300506032b6570032100")
            keys[role] = der[-32:]

        config = {"executors": {"[WORK]": keys["executor"].hex()}, "verifier": keys["verifier"].hex()}
        os.environ["ICARUS_DUTY_AGENT_SIGNERS"] = json.dumps(config)
        with self.assertRaisesRegex(ValueError, "distinct public keys"):
            runner.load_agent_signers(json.dumps({**config, "verifier": keys["executor"].hex()}))

        def sign(receipt, header, role, mailbox_url=outbox):
            _, packet = next(runner.comment_packets([receipt], header))
            message = directory / "signed-input"
            message.write_bytes(runner.agent_receipt_message(mailbox_url, header, packet))
            private = directory / f"{role}.pem"
            signature = subprocess.check_output([
                "openssl", "pkeyutl", "-sign", "-rawin", "-inkey", str(private), "-in", str(message),
            ])
            return receipt["body"] + "\nAgent Signature: " + signature.hex()

        unsigned = verifier["body"]
        worker["body"] = sign(worker, runner.EXECUTION_HEADER, "executor")
        for mode, body in (
            ("unsigned", unsigned),
            ("self-signed", sign(verifier, runner.VERIFICATION_HEADER, "executor")),
            ("different mailbox", sign(verifier, runner.VERIFICATION_HEADER, "verifier", outbox.replace("/6/", "/7/"))),
            ("tampered", sign(verifier, runner.VERIFICATION_HEADER, "verifier").replace(
                "Observed SHA256: " + "a" * 64, "Observed SHA256: " + "b" * 64)),
        ):
            with self.subTest(mode=mode):
                verifier["body"] = body
                self.assertEqual(self.run_pulse()["terminal_receipts"], [])
                self.assertEqual(self.issues[-1]["state"], "open")

        verifier["body"] = unsigned
        verifier["body"] = sign(verifier, runner.VERIFICATION_HEADER, "verifier")
        result = self.run_pulse()["terminal_receipts"][0]
        self.assertEqual((result["status"], result["exit_code"]), ("CLOSED", 0))
        self.assertEqual(result["executor_sha"], hashlib.sha256(keys["executor"]).hexdigest())
        self.assertEqual(result["verifier_sha"], hashlib.sha256(keys["verifier"]).hexdigest())
        self.assertEqual(self.issues[-1]["state"], "closed")
        self.assertEqual(self.run_pulse()["terminal_receipts"], [])

    def test_terminal_exhausted_reissue_leash_leaves_issue_open(self):
        dispatch = self.start_backlog()
        self.terminal_proof(9, dispatch, exit_code=1)
        retry = self.run_pulse()["terminal_receipts"][0]["reissue_comment_id"]
        self.terminal_proof(9, retry, exit_code=1)
        blocked = self.run_pulse()["terminal_receipts"][0]
        self.assertEqual((blocked["verdict"], blocked["status"]), ("FAIL", "BLOCKED"))
        self.assertNotIn("reissue_comment_id", blocked)
        self.assertEqual(self.issues[-1]["state"], "open")
        count = len(self.posts)
        self.run_pulse()
        self.assertEqual(len(self.posts), count)

    def test_terminal_closure_resumes_after_ambiguous_patch_without_repeating_it(self):
        dispatch = self.start_backlog()
        self.terminal_proof(9, dispatch)
        self.ambiguous_patch = True
        failed = self.run_pulse(expected_exit=1)
        self.assertEqual(failed["terminal_receipts"][0]["status"], "ADJUDICATED")
        self.assertIn("response lost", failed["first_processing_error"])
        self.assertEqual(self.run_pulse()["terminal_receipts"][0]["status"], "CLOSED")
        self.assertEqual(sum(method == "PATCH" for method, _ in self.requests), 1)

    def test_issue_six_dispatch_includes_verified_source(self):
        os.environ["ICARUS_PULSE_TRIGGER_SCHEDULE"] = ""
        self.comments[6] = [comment(10, task("LEGACY"))]
        record = self.run_pulse(at=datetime(2026, 12, 31, 15, 7, tzinfo=timezone.utc))
        self.assertEqual(record["new_tasks_dispatched"], 1)
        self.assertEqual(record["dispatch_receipts"][0]["source_comment_id"], 10)
        self.assertEqual(self.posts, [
            "[ICARUS DISPATCH]\nTask ID: LEGACY\nTarget Chair: [WORK]\n"
            "Directive: Inspect the evidence\nBudget: €0.00 | Repair Leash: 1 attempt\n"
            "Source File: harness-runner.py\n"
            f"Source Blob: {record['task_states']['LEGACY']['source_blob']}"
        ])

    def test_named_specialists_receive_their_own_task_packets(self):
        chairs = ("[CODEX]", "[SOL]", "[LUNA]", "[GRACE]")
        self.comments[6] = [
            comment(10 + i, task(f"SPECIALIST-{i}").replace("[WORK]", chair))
            for i, chair in enumerate(chairs)
        ]
        reporters = {chair.strip("[]"): 101 + i for i, chair in enumerate(chairs)}
        self.add_seat_reports(reporters, "available")
        with patch.object(pilot_state, "load_policy", return_value=(
                {"seat_reporters": reporters, "verifier_user_id": None, "approved_pilots": {}}, "digest")):
            record = self.run_pulse()
        self.assertEqual([entry["delegated_to"] for entry in record["dispatch_receipts"]], list(chairs))
        for chair, body in zip(chairs, self.posts):
            self.assertIn(f"Target Chair: {chair}", body)
            self.assertIn("Repair Leash: 1 attempt", body)

    def add_seat_reports(self, reporters, state, at="2026-11-08T14:02:00Z"):
        for i, (seat, uid) in enumerate(reporters.items()):
            row = comment(30 + i, f"{pilot_state.SEAT_REPORT}\nSeat: {seat}\nAvailability: {state}")
            row.update(created_at=at, updated_at=at)
            row["user"]["id"] = uid
            self.comments.setdefault(6, []).append(row)

    def test_unknown_specialist_holds_before_dispatch(self):
        self.comments[6] = [comment(10, task("HOLD").replace("[WORK]", "[CODEX]"))]
        self.assertEqual(self.run_pulse()["held_specialist_routes"], [
            {"task_id": "HOLD", "target_chair": "[CODEX]", "availability": "unknown"},
        ])
        self.assertEqual(self.posts, [])

    def test_empty_registry_keeps_legacy_backlog_route(self):
        self.issues += [
            {**issue(7, title="[P0] [READY] Unenrolled", body="[TO] [CODEX]"), "state": "open"},
            {**issue(8, title="[READY] Existing Sol route", body="[TO] [SOL]"), "state": "open"},
        ]
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule"}):
            record = self.run_pulse()
        self.assertEqual(record["dispatch_receipts"][0]["task_id"], "BACKLOG-8")
        self.assertEqual(record["dispatch_receipts"][0]["delegated_to"], "[SOL]")

    def test_scheduled_pilot_consumes_one_attempt_across_wakes(self):
        number = 88
        task_id = f"BACKLOG-{number}"
        source = "harness-runner.py"
        source_bytes = (Path(__file__).resolve().parents[1] / source).read_bytes()
        expected = hashlib.sha256(source_bytes).hexdigest()
        reporters = {seat: 101 + i for i, seat in enumerate(sorted(pilot_state.SEATS))}
        at = datetime.now(timezone.utc).replace(microsecond=0)
        reported_at = (at - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        self.add_seat_reports(reporters, "unavailable", reported_at)
        self.issues.append({**issue(number, title="[READY] Artifact readback", body="[TO] [CODEX]"), "state": "open"})
        approval = comment(55, f"{pilot_state.PILOT_APPROVAL}\nTask ID: {task_id}\nPolicy SHA-256: digest")
        approval.update(created_at=reported_at, updated_at=reported_at)
        self.comments[141] = [approval]
        policy = {"seat_reporters": reporters, "verifier_user_id": 999,
                  "approved_pilots": {task_id: {"path": source, "sha256": expected}}}
        with (patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule", "GITHUB_ACTIONS": "true",
                                      "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": "a" * 40,
                                      "GITHUB_WORKFLOW_REF": "example/Teamchat/.github/workflows/icarus-pulse.yml@refs/heads/main"}),
              patch.object(pilot_state, "load_policy", return_value=(policy, "digest"))):
            first = self.run_pulse(at=at)
            second = self.run_pulse(at=at)
        self.assertEqual(first["loop_state"], "WAITING_FOR_INDEPENDENT_VERIFIER")
        self.assertEqual(first["pilot_attempt"]["process_exit_code"], 0)
        self.assertEqual(first["pilot_attempt"]["sha256"], expected)
        self.assertEqual((self.ledger.parent / "proof.bin").read_bytes(), source_bytes)
        self.assertIsNone(second["pilot_attempt"])
        self.assertEqual(self.posts, [f"{pilot_state.PILOT_RESERVATION}\nTask ID: {task_id}"])

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
        first = self.run_pulse(at=datetime(2026, 11, 8, 15, 7, tzinfo=timezone.utc))
        self.assertEqual(first["loop_state"], "DISPATCHED")
        self.assertEqual(first["task_states"]["BACKLOG-9"]["status"], "WAITING_FOR_RECEIPT")
        self.assertEqual(first["backlog_claim"]["issue_number"], 9)
        self.assertTrue(self.comments[9][-1]["body"].startswith(runner.CLAIM_HEADER))
        self.assertIn("Source Issue: #9 (comment 10001)", self.comments[6][-1]["body"])
        second = self.run_pulse()
        self.assertEqual(second["backlog_claim"]["issue_number"], 8)
        self.assertEqual(second["waiting_backlog"], [
            {"task_id": "BACKLOG-9", "dispatch_comment_id": 10002},
        ])
        self.assertEqual(set(second["task_states"]), {"BACKLOG-8", "BACKLOG-9"})
        self.assertEqual(second["task_states"]["BACKLOG-9"]["dispatch_comment_id"], 10002)
        self.assertEqual(second["task_states"]["BACKLOG-8"]["dispatch_comment_id"], 10004)
        third = self.run_pulse()
        self.assertEqual(third["loop_state"], "IDLE_SELECT")
        self.assertEqual(third["task_states"], second["task_states"])
        self.assertIsNone(third["backlog_claim"])
        self.assertFalse(third["dispatch_receipts"])
        self.assertEqual(len(self.comments[9]), 1)
        self.assertEqual(len(self.comments[8]), 1)
        self.assertEqual(len(self.posts), 4)

    def test_pending_canary_does_not_block_authorized_backlog(self):
        os.environ["GITHUB_EVENT_NAME"] = "schedule"
        self.comments[6] = canary_comments("CANARY-INTAKE-001")
        self.issues += [
            {**issue(7, title="[P0] [READY] Untrusted", association="CONTRIBUTOR"), "state": "open"},
            {**issue(8, title="[READY] Authorized"), "state": "open"},
        ]
        waiting = [{"task_id": "CANARY-INTAKE-001", "dispatch_comment_id": 11}]

        first = self.run_pulse()
        self.assertEqual(first["waiting_canary"], waiting)
        self.assertFalse(first["adjudication_receipts"])
        self.assertEqual(first["backlog_claim"], {"issue_number": 8, "claim_comment_id": 10001})
        self.assertEqual(first["dispatch_receipts"], [{
            "issue_number": 8, "source_comment_id": 10001, "task_id": "BACKLOG-8",
            "delegated_to": "[WORK]", "dispatch_comment_id": 10002,
        }])
        self.assertEqual(first["task_states"]["CANARY-INTAKE-001"]["status"], "WAITING_FOR_RECEIPT")

        second = self.run_pulse()
        self.assertEqual(second["waiting_canary"], waiting)
        self.assertEqual(second["waiting_backlog"], [
            {"task_id": "BACKLOG-8", "dispatch_comment_id": 10002},
        ])
        self.assertIsNone(second["backlog_claim"])
        self.assertFalse(second["dispatch_receipts"])
        self.assertEqual(len(self.posts), 2)

    def test_preflight_blocked_backlog_is_never_claimed_and_next_task_dispatches(self):
        os.environ["GITHUB_EVENT_NAME"] = "schedule"
        self.issues.extend([
            {**issue(7, title="[P0] [READY] Missing file", body="[SOURCE_FILE] absent.py"),
             "state": "open"},
            {**issue(8, title="[READY] Valid"), "state": "open"},
        ])
        record = self.run_pulse()
        self.assertEqual(record["task_states"]["BACKLOG-7"]["source_preflight"], "SOURCE_FILE_NOT_TRACKED")
        self.assertEqual(record["task_states"]["BACKLOG-7"]["status"], "PREFLIGHT_BLOCKED")
        self.assertFalse(self.comments.get(7))
        self.assertEqual(record["task_states"]["BACKLOG-8"]["status"], "WAITING_FOR_RECEIPT")
        blob = subprocess.check_output(
            ["git", "rev-parse", "HEAD:harness-runner.py"], cwd=runner.REPO_ROOT, text=True,
        ).strip()
        self.assertEqual(record["task_states"]["BACKLOG-8"]["source_blob"], blob)
        self.assertIn(f"Source Blob: {blob}", self.comments[6][-1]["body"])

    def test_invalid_directive_sources_are_isolated_and_valid_dispatch_is_durable(self):
        self.comments[6] = [
            comment(10, task("MISSING", None)),
            comment(11, task("TRAVERSAL", "../harness-runner.py")),
            comment(12, task("AMBIGUOUS") + "\nSource File: icarus/core/duty_runner.py"),
            comment(13, task("DIRECTORY", "icarus")),
            comment(14, task("VALID") + "\nSource Blob: scope text"),
        ]
        record = self.run_pulse()
        self.assertEqual({key: value["source_preflight"] for key, value in record["task_states"].items()}, {
            "MISSING": "SOURCE_FILE_REQUIRED", "TRAVERSAL": "INVALID_SOURCE_PATH",
            "AMBIGUOUS": "AMBIGUOUS_SOURCE_FILE", "DIRECTORY": "SOURCE_FILE_NOT_TRACKED",
            "VALID": "VERIFIED",
        })
        self.assertEqual([receipt["task_id"] for receipt in record["dispatch_receipts"]], ["VALID"])
        self.assertEqual(self.run_pulse()["task_states"]["VALID"], record["task_states"]["VALID"])
        self.assertEqual(len(self.posts), 1)

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
        self.comments[6] = canary_comments(task_id)
        receipt = (
            f"[WORK] EXECUTION RECEIPT\nTask ID: {task_id}\nExecutor: ChatGPT Work\n"
            f"Worker result: ECHO_COMPLETE\nEcho: {directive}\nOwner intake: {link}10\n"
            f"Icarus dispatch: {link}11\nWork claim: {link}12"
        )
        self.comments[6].append(comment(13, receipt, association="CONTRIBUTOR"))
        os.environ["GITHUB_EVENT_NAME"] = "schedule"
        pending = self.run_pulse()
        self.assertEqual(pending["loop_state"], "IDLE_SELECT")
        self.assertEqual(pending["task_states"][task_id]["status"], "WAITING_FOR_RECEIPT")
        self.assertEqual(pending["waiting_canary"], [{"task_id": task_id, "dispatch_comment_id": 11}])
        self.assertFalse(self.posts)
        self.comments[6].append(comment(14, receipt))
        os.environ["GITHUB_EVENT_NAME"] = "workflow_dispatch"
        self.assertFalse(self.run_pulse()["adjudication_receipts"])
        os.environ["GITHUB_EVENT_NAME"] = "schedule"
        first = self.run_pulse()
        self.assertEqual(first["loop_state"], "ADJUDICATED")
        self.assertEqual(first["task_states"][task_id]["status"], "ADJUDICATED")
        self.assertFalse(first["waiting_canary"])
        self.assertEqual(first["adjudication_receipts"][0]["work_receipt_comment_id"], 14)
        self.assertTrue(self.posts[0].startswith(runner.ADJUDICATION_HEADER))
        next_run = self.run_pulse()
        self.assertEqual(next_run["loop_state"], "IDLE_SELECT")
        self.assertEqual(next_run["task_states"][task_id], first["task_states"][task_id])
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

