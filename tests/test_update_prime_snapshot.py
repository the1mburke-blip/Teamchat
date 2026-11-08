import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import update_prime_snapshot as snapshot


class PrimeSnapshotTests(unittest.TestCase):
    def test_comment_tail_crosses_pages_newest_first(self):
        first = [{"id": n} for n in range(1, 6)]
        previous = [{"id": n} for n in range(6, 11)]
        last = [{"id": n} for n in range(11, 14)]
        links = '<https://api.github.com/repositories/123/issues/6/comments?page=3&per_page=5>; rel="last"'
        with patch.object(snapshot, "gh_get", side_effect=[(first, links), (last, ""), previous]) as get:
            self.assertEqual([c["id"] for c in snapshot.latest_team_comments()], [13, 12, 11, 10, 9])
        self.assertEqual([call.args[0] for call in get.call_args_list], [
            "/issues/6/comments?per_page=5", "/issues/6/comments?per_page=5&page=3",
            "/issues/6/comments?per_page=5&page=2",
        ])

    def test_pulse_uses_runner_step_conclusion_separately_from_workflow(self):
        run = {"id": 42, "event": "schedule", "conclusion": "failure"}
        job = {"steps": [{"name": "Execute ICARUS On-Duty Runner", "conclusion": "success"}]}
        with patch.object(snapshot, "gh_get", side_effect=[{"workflow_runs": [run]}, {"jobs": [job]}]):
            self.assertEqual(snapshot.latest_pulse_status(), "run=42 event=schedule workflow=failure runner=success")

    def test_payload_prioritizes_fresh_state_and_is_under_form_limit(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        for filename in ("BUFFER_QUEUE_STATE.md", "CHAT_LOG.md"):
            (root / filename).write_text("stale archive content", encoding="utf-8")
        (root / "STATUS.md").write_text("current operational state", encoding="utf-8")
        commits = [f"abcde{i:02d} Current commit {i}" for i in range(5)]
        comments = [{"id": i, "body": "🚀" * 700} for i in range(19, 14, -1)]
        issues = [{"number": i, "body": "🚀" * 360} for i in range(1, 21)]
        pulse = "run=42 event=schedule workflow=success runner=success"
        output = root / "payload.json"
        with (
            patch.multiple(snapshot, ROOT=root, OUT=output),
            patch.object(snapshot.subprocess, "check_output", return_value="\n".join(commits)) as git,
            patch.object(snapshot, "latest_team_comments", return_value=comments),
            patch.object(snapshot, "latest_pulse_status", return_value=pulse),
            patch.object(snapshot, "gh_get", return_value=issues),
            redirect_stdout(io.StringIO()) as log,
        ):
            snapshot.main()
        git.assert_called_once_with(["git", "log", "-5", "--oneline"], cwd=root, text=True)
        payload = json.loads(output.read_text(encoding="utf-8"))["snapshot"]
        self.assertIn("\n".join(commits), payload)
        self.assertLess(payload.index(commits[-1]), payload.index(pulse))
        self.assertLess(payload.index(pulse), payload.index("### Comment 19"))
        positions = [payload.index(f"### Comment {i}") for i in range(19, 14, -1)]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(positions[-1], payload.index("## Open Teamchat work"))
        self.assertNotIn("stale archive content", payload)
        self.assertLess(len(payload.encode("utf-16-le")) // 2, 14000)
        self.assertTrue(payload.endswith(snapshot.TRUNCATION_NOTICE))
        self.assertIn("issue6_comments=19,18,17,16,15", log.getvalue())
        self.assertNotIn("🚀", log.getvalue())
