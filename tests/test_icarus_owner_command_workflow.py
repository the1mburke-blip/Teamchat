from pathlib import Path
import unittest


class IcarusOwnerCommandWorkflowTests(unittest.TestCase):
    def test_owner_command_is_wired_to_the_canonical_issue(self):
        workflow = Path(".github/workflows/icarus-pulse.yml").read_text(encoding="utf-8")
        self.assertIn("issue_comment:", workflow)
        self.assertIn("github.event.issue.number == 99", workflow)
        self.assertIn("github.event.comment.user.id == 324897963", workflow)
        self.assertIn("github.event.comment.author_association == 'OWNER'", workflow)
        self.assertIn("'[SOL] '", workflow)
        self.assertIn("'ICARUS_RUN '", workflow)
        self.assertIn("python3 -m icarus.core.runtime", workflow)
        self.assertIn("github.rest.issues.createComment", workflow)
        self.assertIn("github.rest.repos.getContent", workflow)
        self.assertIn('ICARUS_ISSUE_NUMBER: "99"', workflow)
        self.assertIn("icarus-issue-99-intake", workflow)


if __name__ == "__main__":
    unittest.main()
