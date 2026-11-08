import io
import os
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs

from scripts import prime_snapshot_sync as sync


VIEW = "https://docs.google.com/forms/d/e/test-id/viewform"
POST = "https://docs.google.com/forms/d/e/test-id/formResponse"


class Response(io.BytesIO):
    status = 200

    def geturl(self):
        return VIEW


class SnapshotAppendTests(unittest.TestCase):
    def test_subsequent_runs_post_fresh_responses_without_edit_state(self):
        requests = []
        page = (
            b'<form action="/forms/d/e/test-id/formResponse">'
            b'<input type="hidden" name="fvv" value="1">'
            b'<input type="hidden" name="edit2" value="fixed-response"></form>'
        )

        def urlopen(request, *, timeout):
            requests.append(request)
            if request.get_method() == "GET":
                return Response(page)
            return Response(b"Your response has been recorded")

        with patch.object(sync.urllib.request, "urlopen", urlopen):
            for run in ("11", "12"):
                sync.append_snapshot(VIEW + "?edit2=fixed-response", {
                    "run_id": run, "marker": "marker", "sequence": "1",
                    "total": "1", "snapshot": "payload",
                })
        self.assertEqual([r.full_url for r in requests], [VIEW, POST, VIEW, POST])
        posted = [parse_qs(r.data.decode()) for r in requests[1::2]]
        self.assertEqual([row["entry.1699301106"] for row in posted], [["11"], ["12"]])
        self.assertTrue(all("edit2" not in row and row["entry.414143502"] == ["payload"] for row in posted))

    def test_does_not_post_to_edit_or_unexpected_form(self):
        with patch.object(sync.urllib.request, "urlopen", return_value=Response(
            b'<form action="/forms/d/e/test-id/editResponse"></form>'
        )) as request:
            with self.assertRaisesRegex(ValueError, "standard submission endpoint"):
                sync.append_snapshot(VIEW, {})
            self.assertEqual(request.call_count, 1)

    def test_rerun_refuses_duplicate_post(self):
        with patch.dict(os.environ, {"GITHUB_RUN_ATTEMPT": "2"}), patch.object(sync, "append_snapshot") as send:
            with self.assertRaisesRegex(SystemExit, "Duplicate Form submission refused"):
                sync.main()
            send.assert_not_called()
