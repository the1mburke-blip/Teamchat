"""Adversarial admission tests. Fake API responses are unit fixtures only."""
import base64
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from dsh.state_write_gate import (
    Git, Rejected, TRUSTED_FILES, WORKFLOW_ID, WORKFLOW_PATH, REPOSITORY_ID,
    audit, digest, manifest_from_archive, parse, receipt_schema, verify_receipt,
)


BASE, SOURCE, HEAD = "a" * 40, "b" * 40, "c" * 40
STATE = b"history\n[STATUS] PASS\n"


class ProofFixture:
    def __init__(self):
        self.manifest = {"evaluator": "CHAIR_JUDGE", "verdict": "PASS",
            "readback_status": "VERIFIED", "exit_code": 0,
            "repository_id": REPOSITORY_ID, "source_commit": SOURCE,
            "harness_run_id": 12, "run_attempt": 1, "task_id": "PR-9",
            "artifacts": {"CHAT_LOG.md": digest(STATE)}}
        self.buffer = io.BytesIO()
        with zipfile.ZipFile(self.buffer, "w") as archive:
            archive.writestr("COMPLETION_MANIFEST.json", json.dumps(self.manifest))
            archive.writestr("RUN_LOG.jsonl", "{}\n")
        self.raw = self.buffer.getvalue()
        self.receipt = {"version": 1, "task_id": "PR-9", "harness_run_id": 12,
            "run_attempt": 1, "artifact_id": 13, "artifact_sha256": digest(self.raw),
            "source_commit": SOURCE, "artifacts": {"CHAT_LOG.md": digest(STATE)}}
        self.run_data = {"id": 12, "run_attempt": 1, "status": "completed",
            "conclusion": "success", "head_sha": SOURCE, "workflow_id": WORKFLOW_ID,
            "path": WORKFLOW_PATH, "repository": {"id": REPOSITORY_ID},
            "head_repository": {"id": REPOSITORY_ID}, "event": "pull_request"}
        self.job_data = {"total_count": 1, "jobs": [{"name": "harness",
            "status": "completed", "conclusion": "success"}]}
        self.artifact = {"id": 13, "name": "harness-run-log-12-1", "expired": False,
            "digest": "sha256:" + digest(self.raw)}

    def get(self, suffix):
        if suffix.startswith("/contents/"):
            return {"encoding": "base64", "content": base64.b64encode(b"trusted").decode()}
        if suffix.endswith("/artifacts?per_page=100"):
            return {"total_count": 1, "artifacts": [self.artifact]}
        if "/jobs?" in suffix:
            return self.job_data
        return self.run_data

    def archive(self, artifact_id):
        assert artifact_id == 13
        return self.raw

    def run(self, *args):
        return (SOURCE + "\n").encode()

    def changed(self, base, head):
        return [".icarus/receipts/proof.json"]

    def blob(self, ref, path):
        return STATE if path == "CHAT_LOG.md" else b"trusted"


class RemoteProofTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ProofFixture()

    def verify(self):
        f = self.fixture
        return verify_receipt(f.receipt, f, f, BASE, HEAD)

    def test_authenticated_matching_proof_is_admitted(self):
        self.assertEqual(self.verify(), {"CHAT_LOG.md"})

    def test_self_signed_receipt_cannot_supply_its_own_run(self):
        with patch.object(self.fixture, "get", return_value={}):
            with self.assertRaises(Rejected):
                self.verify()

    def test_wrong_identity_and_stale_attempts_are_rejected(self):
        for key, value in [("head_sha", HEAD), ("workflow_id", 1),
                           ("run_attempt", 2), ("event", "workflow_dispatch"),
                           ("conclusion", "cancelled")]:
            with self.subTest(key=key):
                f = ProofFixture()
                f.run_data[key] = value
                with self.assertRaises(Rejected):
                    verify_receipt(f.receipt, f, f, BASE, HEAD)

    def test_failed_harness_and_unrelated_failures_are_rejected(self):
        self.fixture.job_data["jobs"][0]["conclusion"] = "failure"
        with self.assertRaises(Rejected):
            self.verify()

    def test_receipt_bootstrap_accepts_only_admission_failure(self):
        self.fixture.run_data["conclusion"] = "failure"
        self.fixture.job_data["jobs"].append({"name": "completion-integrity", "conclusion": "failure"})
        self.fixture.job_data["total_count"] = 2
        self.assertEqual(self.verify(), {"CHAT_LOG.md"})
        self.fixture.job_data["jobs"][1]["name"] = "another-job"
        with self.assertRaises(Rejected):
            self.verify()

    def test_download_hash_and_server_hash_are_checked(self):
        self.fixture.raw += b"tampered"
        with self.assertRaises(Rejected):
            self.verify()
        self.fixture = ProofFixture()
        self.fixture.artifact["digest"] = "sha256:" + "0" * 64
        with self.assertRaises(Rejected):
            self.verify()

    def test_state_changes_after_execution_are_rejected(self):
        with patch.object(self.fixture, "changed", return_value=["CHAT_LOG.md"]):
            with self.assertRaises(Rejected):
                self.verify()

    def test_forged_state_hash_is_rejected(self):
        self.fixture.receipt["artifacts"]["CHAT_LOG.md"] = "0" * 64
        with self.assertRaises(Rejected):
            self.verify()

    def test_modified_producer_is_rejected(self):
        with patch.object(self.fixture, "blob", return_value=b"different producer"):
            with self.assertRaises(Rejected):
                self.verify()

    def test_expired_and_ambiguous_proof_is_rejected(self):
        self.fixture.artifact["expired"] = True
        with self.assertRaises(Rejected):
            self.verify()

    def test_strict_receipt_schema(self):
        for key, value in [("run_attempt", True), ("source_commit", "bad"),
                           ("artifact_sha256", "bad"), ("extra", 1)]:
            with self.subTest(key=key):
                receipt = copy.deepcopy(self.fixture.receipt)
                receipt[key] = value
                with self.assertRaises(Rejected):
                    receipt_schema(receipt)

    def test_duplicate_json_is_rejected(self):
        with self.assertRaises(Rejected):
            parse('{"verdict":"FAIL","verdict":"PASS"}')

    def test_archive_member_is_not_extracted(self):
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, "w") as archive:
            archive.writestr("../outside", "payload")
        with self.assertRaises(Rejected):
            manifest_from_archive(raw.getvalue())


class RealGitAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.git = Git(self.root)
        self.git.run("init", "-q")
        self.git.run("config", "user.name", "Gate test")
        self.git.run("config", "user.email", "gate@example.invalid")
        (self.root / "CHAT_LOG.md").write_text("history\n")
        (self.root / "STATUS.md").write_text("REQUESTED\n")
        self.commit()
        self.base = self.git.run("rev-parse", "HEAD").decode().strip()

    def tearDown(self):
        self.tmp.cleanup()

    def commit(self):
        self.git.run("add", ".")
        self.git.run("commit", "-qm", "fixture")
        return self.git.run("rev-parse", "HEAD").decode().strip()

    def test_unverified_pass_is_physically_rejected(self):
        (self.root / "CHAT_LOG.md").write_text("history\n[STATUS] PASS\n")
        with self.assertRaises(Rejected):
            audit(self.git, self.base, self.commit())

    def test_state_register_change_without_receipt_is_rejected(self):
        (self.root / "STATUS.md").write_text("COMPLETED\n")
        with self.assertRaises(Rejected):
            audit(self.git, self.base, self.commit())

    def test_history_rewrite_is_rejected(self):
        (self.root / "CHAT_LOG.md").write_text("rewritten\n")
        with self.assertRaises(Rejected):
            audit(self.git, self.base, self.commit())

    def test_nonterminal_log_append_is_allowed(self):
        (self.root / "CHAT_LOG.md").write_text("history\n[STATUS] INFO\n")
        self.assertEqual(audit(self.git, self.base, self.commit())["completion_claims"], 0)

    def test_nonstate_code_change_does_not_need_receipt(self):
        (self.root / "example.py").write_text("value = 1\n")
        self.assertEqual(audit(self.git, self.base, self.commit())["audit"], "PASS")

    def test_cli_fails_closed_without_origin(self):
        runner = Path(__file__).resolve().parents[1] / "harness-runner.py"
        result = subprocess.run([sys.executable, str(runner), "--audit-state-writes"],
                                cwd=self.root, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 1)
        self.assertIn("FRAUDULENT_OR_UNVERIFIED_COMPLETION_CLAIM", result.stdout)


if __name__ == "__main__":
    unittest.main()
