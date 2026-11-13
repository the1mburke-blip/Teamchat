"""Tier 1 machine tests for harness-runner-v3.py and icarus_pilot.py (stdlib unittest only)."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "canary_init.json"


def load_harness():
    spec = importlib.util.spec_from_file_location("harness_runner_v3", ROOT / "harness-runner-v3.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_repo(tmp: Path, commit=True) -> Path:
    (tmp / "schemas").mkdir()
    shutil.copy(ROOT / "schemas" / "task_packet.v3.schema.json", tmp / "schemas")
    for d in ("task_queue", "processed", "icarus/runs"):
        (tmp / d).mkdir(parents=True)
        (tmp / d / ".gitkeep").write_text("")
    shutil.copy(ROOT / "harness-runner-v3.py", tmp)
    shutil.copy(ROOT / "icarus_pilot.py", tmp)
    if commit:
        for args in (["init", "-q"], ["add", "-A"],
                     ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"]):
            subprocess.run(["git", *args], cwd=tmp, check=True, capture_output=True)
    return tmp


def packet(tid="T-ONE-001", cmd=None, outputs=None, limit=3, timeout=30, extra=None, stages=None):
    p = {
        "template_version": "v3.0.0", "task_id": tid, "title": "t", "objective": "o",
        "proposed_by": "test", "assigned_executor": "unittest",
        "stages": stages or [{
            "stage_id": "S1", "name": "s1",
            "command": cmd or ["python3", "-c", "print('ok')"],
            "expected_outputs": outputs if outputs is not None else ["icarus/runs/artifacts/t/out.txt"],
            "attempt_limit": limit, "timeout_seconds": timeout}],
        "adjudication": {"verifier_tier": "TIER_1_MACHINE"},
        "acceptance_criteria": {"success_condition": "x", "verification_file": "icarus/runs/RUN_LOG.jsonl"},
    }
    p.update(extra or {})
    return p


WRITE_OK = ["python3", "-c",
            "import os;os.makedirs('icarus/runs/artifacts/t',exist_ok=True);open('icarus/runs/artifacts/t/out.txt','w').write('hello')"]


class HarnessCase(unittest.TestCase):
    def setUp(self):
        self._env = mock.patch.dict(os.environ)
        self._env.start()
        for k in ("GITHUB_TOKEN", "GITHUB_REPOSITORY", "GITHUB_SHA"):
            os.environ.pop(k, None)
        self.tmp = Path(tempfile.mkdtemp())
        make_repo(self.tmp)
        self.h = load_harness()
        self.h.REPO = self.tmp

    def tearDown(self):
        self._env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_packet(self, pkt, name="p.json"):
        f = self.tmp / "task_queue" / name
        f.write_text(json.dumps(pkt))
        return self.h.execute_packet(f)


class SchemaTests(HarnessCase):
    def schema(self):
        return json.loads((self.tmp / "schemas/task_packet.v3.schema.json").read_text())

    def test_valid_packet_has_no_errors(self):
        self.assertEqual(self.h.validate(packet(), self.schema()), [])

    def test_missing_required_field(self):
        p = packet()
        del p["objective"]
        self.assertTrue(any("objective" in e for e in self.h.validate(p, self.schema())))

    def test_additional_property_rejected(self):
        self.assertTrue(self.h.validate(packet(extra={"surprise": 1}), self.schema()))

    def test_attempt_limit_above_three_rejected(self):
        self.assertTrue(self.h.validate(packet(limit=4), self.schema()))

    def test_timeout_above_300_rejected(self):
        self.assertTrue(self.h.validate(packet(timeout=301), self.schema()))

    def test_output_outside_artifacts_rejected(self):
        self.assertTrue(self.h.validate(packet(outputs=["../etc/passwd"]), self.schema()))


class SecretTests(HarnessCase):
    def test_detects_and_redacts_github_token(self):
        tok = "ghp_" + "a" * 36
        self.assertTrue(self.h.find_secrets("x " + tok))
        self.assertNotIn(tok, self.h.redact("x " + tok))

    def test_plain_text_is_clean(self):
        self.assertEqual(self.h.find_secrets("hello world run_id 123"), [])


class GateTests(HarnessCase):
    def test_pass_path_writes_receipt_and_readback(self):
        r = self.run_packet(packet(cmd=WRITE_OK))
        rc = r["receipt"]
        self.assertEqual(rc["status"], "PASS", json.dumps(rc["gate_2_policy"]))
        self.assertTrue(rc["gate_1_technical"]["passed"] and rc["gate_2_policy"]["passed"])
        self.assertTrue(r["appended"])
        self.assertTrue(r["readback"]["receipt_hash_matches"] and r["readback"]["artifacts_rehashed_ok"])
        self.assertEqual(self.h.verify_ledger()["lines"], 1)
        self.assertFalse(rc["signed"])
        self.assertEqual(rc["verifier_tier"], "TIER_1_MACHINE")

    def test_missing_expected_output_fails_gate1(self):
        r = self.run_packet(packet())  # prints ok, writes nothing
        self.assertEqual(r["receipt"]["status"], "FAIL")
        self.assertFalse(r["receipt"]["gate_1_technical"]["physical_output_files_exist"])

    def test_nonzero_exit_fails_and_identical_failure_is_not_retried(self):
        r = self.run_packet(packet(cmd=["python3", "-c", "import sys;sys.exit(2)"], outputs=[], limit=3))
        self.assertEqual(r["receipt"]["status"], "FAIL")
        att = r["receipt"]["stages"][0]["attempts"]
        self.assertEqual(len(att), 2)
        self.assertIn("blind retry prohibited", att[-1]["stopped"])

    def test_retry_with_changed_failure_then_success(self):
        code = ("import os,sys;c='icarus/runs/artifacts/t/n';os.makedirs('icarus/runs/artifacts/t',exist_ok=True);"
                "n=int(open(c).read()) if os.path.exists(c) else 0;open(c,'w').write(str(n+1));"
                "sys.stderr.write('fail %d'%n) if n<1 else open('icarus/runs/artifacts/t/out.txt','w').write('ok')\n"
                "sys.exit(1 if n<1 else 0)")
        r = self.run_packet(packet(cmd=["python3", "-c", code]))
        self.assertEqual(r["receipt"]["status"], "PASS", json.dumps(r["receipt"]["stages"])[:600])
        self.assertEqual(len(r["receipt"]["stages"][0]["attempts"]), 2)

    def test_timeout_fails(self):
        r = self.run_packet(packet(cmd=["python3", "-c", "import time;time.sleep(10)"], outputs=[], timeout=1, limit=1))
        self.assertEqual(r["receipt"]["status"], "FAIL")
        self.assertTrue(r["receipt"]["stages"][0]["attempts"][0]["timed_out"])

    def test_no_git_sha_fails_gate1(self):
        shutil.rmtree(self.tmp / ".git")
        r = self.run_packet(packet(cmd=WRITE_OK))
        self.assertFalse(r["receipt"]["gate_1_technical"]["git_sha_logged"])
        self.assertEqual(r["receipt"]["status"], "FAIL")

    def test_stale_output_cannot_satisfy_a_new_attempt(self):
        stale = self.tmp / "icarus/runs/artifacts/t"
        stale.mkdir(parents=True)
        (stale / "out.txt").write_text("stale")
        r = self.run_packet(packet())  # command does not write
        self.assertEqual(r["receipt"]["status"], "FAIL")


class PolicyTests(HarnessCase):
    def marker(self):
        return self.tmp / "ran.marker"

    def cmd_touch(self, extra=""):
        return ["python3", "-c", f"open('ran.marker','w').write('x')#{extra}"]

    def test_non_python_command_blocked_without_running(self):
        r = self.run_packet(packet(cmd=["bash", "-c", "touch ran.marker"], outputs=[]))
        self.assertEqual(r["receipt"]["status"], "BLOCKED")
        self.assertFalse(r["receipt"]["gate_2_policy"]["command_scope_ok"])
        self.assertFalse(self.marker().exists())

    def test_pip_module_blocked(self):
        r = self.run_packet(packet(cmd=["python3", "-m", "pip", "install", "x"], outputs=[]))
        self.assertEqual(r["receipt"]["status"], "BLOCKED")

    def test_packet_negative_constraint_vetoes_before_run(self):
        pkt = packet(cmd=self.cmd_touch("buffer.com"), outputs=[],
                     extra={"negative_constraints": [{"id": "NC_X", "description": "d", "forbidden_patterns": ["buffer.com"]}]})
        r = self.run_packet(pkt)
        self.assertEqual(r["receipt"]["status"], "BLOCKED")
        self.assertFalse(r["receipt"]["gate_2_policy"]["negative_constraints_met"])
        self.assertFalse(self.marker().exists())

    def test_builtin_notebook_ui_constraint(self):
        r = self.run_packet(packet(cmd=self.cmd_touch("notebooklm.google.com"), outputs=[]))
        self.assertEqual(r["receipt"]["status"], "BLOCKED")
        self.assertFalse(self.marker().exists())

    def test_builtin_main_push_constraint(self):
        r = self.run_packet(packet(cmd=self.cmd_touch("git push origin main"), outputs=[]))
        self.assertEqual(r["receipt"]["status"], "BLOCKED")

    def test_secret_in_packet_blocks(self):
        r = self.run_packet(packet(cmd=self.cmd_touch("ghp_" + "b" * 36), outputs=[]))
        self.assertEqual(r["receipt"]["status"], "BLOCKED")
        self.assertFalse(self.marker().exists())
        self.assertNotIn("ghp_" + "b" * 36, (self.tmp / "icarus/runs/RUN_LOG.jsonl").read_text())

    def test_secret_in_output_file_blocks_and_is_redacted_on_disk(self):
        tok = "ghp_" + "c" * 36
        cmd = ["python3", "-c",  # token is assembled at runtime so the packet itself stays clean
               "import os;os.makedirs('icarus/runs/artifacts/t',exist_ok=True);"
               "open('icarus/runs/artifacts/t/out.txt','w').write('ghp_'+'c'*36)"]
        r = self.run_packet(packet(cmd=cmd))
        self.assertEqual(r["receipt"]["status"], "BLOCKED")
        self.assertFalse(r["receipt"]["gate_2_policy"]["zero_secrets_detected"])
        self.assertTrue(r["receipt"]["artifacts"][0].get("redacted"))
        self.assertNotIn(tok, (self.tmp / "icarus/runs/artifacts/t/out.txt").read_text())
        self.assertNotIn(tok, (self.tmp / "icarus/runs/RUN_LOG.jsonl").read_text())

    def test_secret_in_stdout_blocks_and_is_redacted_in_receipt(self):
        tok = "ghp_" + "d" * 36
        cmd = ["python3", "-c",
               "import os;os.makedirs('icarus/runs/artifacts/t',exist_ok=True);"
               "open('icarus/runs/artifacts/t/out.txt','w').write('ok');print('ghp_'+'d'*36)"]
        r = self.run_packet(packet(cmd=cmd))
        self.assertEqual(r["receipt"]["status"], "BLOCKED")
        self.assertTrue(r["receipt"]["pre_execution"]["ledger_ok"])
        self.assertTrue(r["receipt"]["stages"][0]["attempts"][0]["secret_hits"] >= 1)
        self.assertNotIn(tok, (self.tmp / "icarus/runs/RUN_LOG.jsonl").read_text())

    def test_stage_does_not_inherit_github_token(self):
        os.environ["GITHUB_TOKEN"] = "not-a-real-token-but-must-not-leak"
        cmd = ["python3", "-c",
               "import os;os.makedirs('icarus/runs/artifacts/t',exist_ok=True);"
               "open('icarus/runs/artifacts/t/out.txt','w').write(str('GITHUB_TOKEN' in os.environ))"]
        self.run_packet(packet(cmd=cmd))
        self.assertEqual((self.tmp / "icarus/runs/artifacts/t/out.txt").read_text(), "False")

    def test_invalid_json_packet_blocked(self):
        f = self.tmp / "task_queue" / "bad.json"
        f.write_text("{not json")
        r = self.h.execute_packet(f)
        self.assertEqual(r["receipt"]["status"], "BLOCKED")
        self.assertFalse(r["receipt"]["gate_2_policy"]["schema_valid"])


class LedgerTests(HarnessCase):
    def two_runs(self):
        self.run_packet(packet(tid="T-ONE-001", cmd=WRITE_OK), "a.json")
        self.run_packet(packet(tid="T-TWO-002", cmd=WRITE_OK), "b.json")

    def test_chain_links_receipts(self):
        self.two_runs()
        lines = [json.loads(x) for x in (self.tmp / "icarus/runs/RUN_LOG.jsonl").read_text().splitlines()]
        self.assertEqual(lines[0]["prev_receipt_hash"], "0" * 64)
        self.assertEqual(lines[1]["prev_receipt_hash"], lines[0]["receipt_hash"])
        self.assertTrue(self.h.verify_ledger()["ok"])

    def test_tampered_receipt_is_detected_and_blocks_new_runs(self):
        self.two_runs()
        p = self.tmp / "icarus/runs/RUN_LOG.jsonl"
        p.write_text(p.read_text().replace('"PASS"', '"FAIL"', 1))
        self.assertFalse(self.h.verify_ledger()["ok"])
        before = p.read_text()
        r = self.run_packet(packet(tid="T-THREE-003", cmd=WRITE_OK), "c.json")
        self.assertEqual(r["receipt"]["status"], "BLOCKED")
        self.assertFalse(r["appended"])
        self.assertEqual(p.read_text(), before)

    def test_deleted_line_breaks_chain(self):
        self.two_runs()
        p = self.tmp / "icarus/runs/RUN_LOG.jsonl"
        p.write_text(p.read_text().splitlines()[1] + "\n")
        self.assertFalse(self.h.verify_ledger()["ok"])

    def test_rewrite_of_committed_history_is_detected(self):
        self.run_packet(packet(tid="T-ONE-001", cmd=WRITE_OK), "a.json")
        env = ["-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(["git", "add", "-A"], cwd=self.tmp, check=True, capture_output=True)
        subprocess.run(["git", *env, "commit", "-qm", "ledger"], cwd=self.tmp, check=True, capture_output=True)
        self.assertEqual(self.h.verify_ledger()["head_check"], "OK")
        p = self.tmp / "icarus/runs/RUN_LOG.jsonl"
        good = p.read_text()
        p.write_text("")  # truncating committed history must be flagged
        v = self.h.verify_ledger()
        self.assertEqual(v["head_check"], "MISMATCH")
        self.assertFalse(v["ok"])
        p.write_text(good)
        self.assertTrue(self.h.verify_ledger()["ok"])

    def test_cli_verify_ledger_exit_codes(self):
        cli = [sys.executable, str(self.tmp / "harness-runner-v3.py"), "--verify-ledger"]
        self.assertEqual(subprocess.run(cli, cwd=self.tmp, capture_output=True).returncode, 0)
        (self.tmp / "icarus/runs/RUN_LOG.jsonl").write_text("garbage\n")
        self.assertEqual(subprocess.run(cli, cwd=self.tmp, capture_output=True).returncode, 1)


class PilotTests(HarnessCase):
    def test_canary_fixture_end_to_end_through_pilot(self):
        shutil.copy(FIXTURE, self.tmp / "task_queue" / "canary_init.json")
        env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_TOKEN", "GITHUB_REPOSITORY")}
        p = subprocess.run([sys.executable, "icarus_pilot.py"], cwd=self.tmp, capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        out = json.loads(p.stdout)
        res = out["results"][0]
        self.assertEqual(res["status"], "PASS")
        self.assertTrue(res["readback"]["receipt_hash_matches"] and res["readback"]["artifacts_rehashed_ok"])
        self.assertTrue(res["archived_to"].endswith("__PASS.json"))
        self.assertFalse((self.tmp / "task_queue" / "canary_init.json").exists())
        readback = json.loads((self.tmp / "icarus/runs/artifacts/canary/canary_readback.json").read_text())
        self.assertTrue(readback["verified"])
        self.assertEqual(readback["run_id"], res["run_id"])

    def test_empty_queue_is_listening_and_exits_zero(self):
        p = subprocess.run([sys.executable, "icarus_pilot.py"], cwd=self.tmp, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(json.loads(p.stdout)["state"], "LISTENING")

    def test_failing_packet_exits_nonzero_and_is_archived_not_rerun(self):
        (self.tmp / "task_queue" / "bad.json").write_text(json.dumps(packet(cmd=["python3", "-c", "import sys;sys.exit(3)"], outputs=[], limit=1)))
        p = subprocess.run([sys.executable, "icarus_pilot.py"], cwd=self.tmp, capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)
        self.assertTrue(any(n.endswith("__FAIL.json") for n in os.listdir(self.tmp / "processed")))
        self.assertFalse((self.tmp / "task_queue" / "bad.json").exists())


if __name__ == "__main__":
    unittest.main()


class SubdirTests(unittest.TestCase):
    """The harness must work when its folder is a subdirectory of a larger git repo (Teamchat layout)."""

    def setUp(self):
        self._env = mock.patch.dict(os.environ)
        self._env.start()
        for k in ("GITHUB_TOKEN", "GITHUB_REPOSITORY", "GITHUB_SHA"):
            os.environ.pop(k, None)
        self.root = Path(tempfile.mkdtemp())
        (self.root / "other.txt").write_text("unrelated")
        self.sub = self.root / "loop-v3"
        self.sub.mkdir()
        make_repo(self.sub, commit=False)
        for args in (["init", "-q"], ["add", "-A"],
                     ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"]):
            subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)
        self.h = load_harness()
        self.h.REPO = self.sub

    def tearDown(self):
        self._env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_head_check_works_from_subdirectory(self):
        f = self.sub / "task_queue" / "p.json"
        f.write_text(json.dumps(packet(cmd=WRITE_OK)))
        r = self.h.execute_packet(f)
        self.assertEqual(r["receipt"]["status"], "PASS")
        self.assertRegex(r["receipt"]["git_sha"], r"^[0-9a-f]{40}$")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "ledger"],
                       cwd=self.root, check=True, capture_output=True)
        self.assertEqual(self.h.verify_ledger()["head_check"], "OK")
        (self.sub / "icarus/runs/RUN_LOG.jsonl").write_text("")
        v = self.h.verify_ledger()
        self.assertEqual(v["head_check"], "MISMATCH")
        self.assertFalse(v["ok"])
