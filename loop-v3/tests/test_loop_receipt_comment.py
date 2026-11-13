"""Tests for receipt_comment.py (the Issue #6 receipt body)."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("receipt_comment", ROOT / "receipt_comment.py")
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)

RECEIPT = {
    "run_id": "R1", "task_id": "T-ONE-001", "status": "PASS", "finished_at": "2026-11-13T12:00:00Z",
    "git_sha": "a" * 40, "receipt_hash": "b" * 64,
    "gate_1_technical": {"passed": True, "exit_code_zero": True, "physical_output_files_exist": True, "git_sha_logged": True},
    "gate_2_policy": {"passed": True, "schema_valid": True, "zero_secrets_detected": True, "negative_constraints_met": True},
    "artifacts": [{"path": "icarus/runs/artifacts/t/out.txt", "sha256": "c" * 64}],
}


class ReceiptCommentTests(unittest.TestCase):
    def test_body_has_prefix_hash_and_gates(self):
        b = rc.build_body(RECEIPT, False, "", "https://example/run/1")
        self.assertTrue(b.startswith("[HARNESS-V3] 2026-11-13T12:00:00Z"))
        self.assertIn("receipt_hash=" + "b" * 64, b)
        self.assertIn("GATE_1: True", b)
        self.assertIn("NOT independently adjudicated", b)

    def test_unsigned_unless_signed_and_url(self):
        self.assertIn("SIGNED: no", rc.build_body(RECEIPT, False, "https://a/b", ""))
        self.assertIn("SIGNED: no", rc.build_body(RECEIPT, True, "", ""))
        self.assertIn("SIGNED: yes", rc.build_body(RECEIPT, True, "https://a/b", ""))

    def test_cli_reads_last_ledger_line_and_empty_ledger_fails(self):
        d = Path(tempfile.mkdtemp())
        led = d / "l.jsonl"
        led.write_text(json.dumps({**RECEIPT, "run_id": "OLD"}) + "\n" + json.dumps(RECEIPT) + "\n")
        self.assertEqual(rc.last_receipt(led)["run_id"], "R1")
        led.write_text("")
        with self.assertRaises(SystemExit):
            rc.last_receipt(led)


if __name__ == "__main__":
    unittest.main()
