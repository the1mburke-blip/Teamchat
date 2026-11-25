import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from icarus.core import duty_runner as runner

REPO = "the1mburke-blip/Teamchat"
ISSUE = f"https://api.github.com/repos/{REPO}/issues/300"


def row(cid, body, association="OWNER", url=None):
    return {"id": cid, "body": body, "author_association": association, "issue_url": ISSUE,
            "html_url": url or f"https://github.com/{REPO}/issues/300#issuecomment-{cid}"}


class ClaimReviewTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (root / "docs").mkdir()
        (root / "docs" / "done.md").write_text("done", encoding="utf-8")
        self.rows, self.thread, self.posts = [], [], []
        self.commits = {"abc1234"}

        def api(url, token, method="GET", payload=None):
            if "/commits/" in url:
                if url.rsplit("/", 1)[-1] in self.commits:
                    return {}, ""
                raise RuntimeError(f"GET {url}: HTTP Error 422")
            return list(self.rows), ""

        def post(url, token, body):
            self.posts.append(body)
            self.thread.append({"id": 900 + len(self.posts), "body": body})
            return 900 + len(self.posts)
        self.enterContext(patch.multiple(
            runner, REPO_ROOT=root, call_github_api=api, post_comment=post,
            fetch_pages=lambda url, token: list(self.thread)))
        self.record = {"claim_reviews": []}

    def review(self):
        runner.review_claims(REPO, "token", self.record)
        return self.record["claim_reviews"]

    def test_pass_claim_with_existing_file_and_commit_passes(self):
        self.rows = [row(1, "[CLAUDE] done\nSTATUS: PASS\nEVIDENCE: docs/done.md at commit abc1234")]
        self.assertEqual(self.review()[0]["verdict"], "PASS")
        self.assertTrue(self.posts[0].startswith("[ICARUS CLAIM REVIEW] PASS\nClaim comment: 1"))

    def test_pass_claim_with_missing_evidence_fails(self):
        self.rows = [row(2, "STATUS: PASS\nEVIDENCE: docs/missing.md and commit def5678")]
        self.assertEqual(self.review()[0]["verdict"], "FAIL")
        self.assertIn("FAIL: file docs/missing.md: exists on main=False", self.posts[0])
        self.assertIn("FAIL: commit def5678: exists=False", self.posts[0])

    def test_pass_claim_without_checkable_evidence_fails(self):
        self.rows = [row(3, "STATUS: PASS\nEVIDENCE: it works, trust me")]
        self.assertEqual(self.review()[0]["verdict"], "FAIL")
        self.assertIn("names no checkable evidence", self.posts[0])

    def test_claim_is_reviewed_once(self):
        self.rows = [row(4, "STATUS: PASS\nEVIDENCE: docs/done.md")]
        self.review()
        self.record = {"claim_reviews": []}
        self.assertEqual(self.review(), [])
        self.assertEqual(len(self.posts), 1)

    def test_untrusted_partial_pr_and_own_output_are_ignored(self):
        self.rows = [
            row(5, "STATUS: PASS\nEVIDENCE: docs/done.md", association="NONE"),
            row(6, "STATUS: PARTIAL\nEVIDENCE: docs/done.md"),
            row(7, "STATUS: PASS\nEVIDENCE: docs/done.md", url=f"https://github.com/{REPO}/pull/9#issuecomment-7"),
            row(8, "[ICARUS CLAIM REVIEW] PASS\nSTATUS: PASS"),
            row(9, "RULE_APPLICATION_STATUS: PASS"),
        ]
        self.assertEqual(self.review(), [])
        self.assertEqual(self.posts, [])

    def test_path_traversal_is_not_evidence(self):
        self.rows = [row(10, "STATUS: PASS\nEVIDENCE: ../etc/passwd.txt")]
        self.review()
        self.assertNotIn("ok: file ../", self.posts[0])

    def test_reviews_are_capped_per_run(self):
        self.rows = [row(20 + i, f"STATUS: PASS\nEVIDENCE: docs/done.md #{i}") for i in range(8)]
        self.assertEqual(len(self.review()), runner.MAX_CLAIM_REVIEWS_PER_RUN)


if __name__ == "__main__":
    unittest.main()
