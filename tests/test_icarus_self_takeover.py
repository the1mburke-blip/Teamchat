import datetime
import unittest
from unittest.mock import patch

from icarus.core import duty_runner as runner

NOW = datetime.datetime(2026, 11, 25, 18, 0, tzinfo=datetime.timezone.utc)


def c(body, at="2026-11-25T12:00:00Z", bot=False):
    return {"body": body, "created_at": at, "user": {"type": "Bot" if bot else "User"}}


class SelfTakeoverTests(unittest.TestCase):
    def setUp(self):
        self.dispatch_at = {10: "2026-11-25T08:00:00Z", 11: "2026-11-25T16:00:00Z"}
        self.threads = {}

        def api(url, token, method="GET", payload=None):
            return {"created_at": self.dispatch_at[int(url.rsplit("/", 1)[-1])]}, ""
        self.enterContext(patch.multiple(
            runner, call_github_api=api,
            fetch_pages=lambda url, token: list(self.threads.get(int(url.split("/")[-2]), []))))

    def pick(self, held=(), states=None):
        record = {"held_specialist_routes": [{"task_id": t} for t in held],
                  "task_states": states or {}, "self_task": None}
        runner.select_self_task("o/r", "t", record, 6, now=NOW)
        return record["self_task"]

    def test_held_task_is_taken_first(self):
        task = self.pick(held=["BACKLOG-7"], states={"BACKLOG-9": {"status": "WAITING_FOR_RECEIPT", "dispatch_comment_id": 10}})
        self.assertEqual(task["issue_number"], 7)
        self.assertIn("held", task["reason"])

    def test_stale_dispatch_without_worker_activity_is_taken(self):
        task = self.pick(states={"BACKLOG-9": {"status": "WAITING_FOR_RECEIPT", "dispatch_comment_id": 10}})
        self.assertEqual(task["issue_number"], 9)

    def test_recent_dispatch_is_left_with_its_agent(self):
        self.assertIsNone(self.pick(states={"BACKLOG-9": {"status": "WAITING_FOR_RECEIPT", "dispatch_comment_id": 11}}))

    def test_worker_activity_after_dispatch_keeps_the_task_with_the_worker(self):
        self.threads[9] = [c("[CLAUDE]\nSTATUS: CLAIMED", at="2026-11-25T09:00:00Z")]
        self.assertIsNone(self.pick(states={"BACKLOG-9": {"status": "WAITING_FOR_RECEIPT", "dispatch_comment_id": 10}}))

    def test_bot_status_text_is_not_worker_activity(self):
        self.threads[9] = [c("STATUS: CLAIMED", at="2026-11-25T09:00:00Z", bot=True)]
        self.assertEqual(self.pick(states={"BACKLOG-9": {"status": "WAITING_FOR_RECEIPT", "dispatch_comment_id": 10}})["issue_number"], 9)

    def test_one_takeover_per_task(self):
        self.threads[7] = [c("[ICARUS via runtime] TAKEOVER BLOCKED: needs store access", bot=True)]
        self.assertIsNone(self.pick(held=["BACKLOG-7"]))

    def test_adjudicated_tasks_and_the_mailbox_are_skipped(self):
        self.assertIsNone(self.pick(held=["BACKLOG-6"], states={"BACKLOG-9": {"status": "ADJUDICATED", "dispatch_comment_id": 10}}))


if __name__ == "__main__":
    unittest.main()
