"""Tier 1 machine tests: unattended runner, fail-closed ingress, restart recovery, independent completion gate."""
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["harness-runner-v3.py", "completion_gate.py", "task_runner.py", "ingress_policy.json"]


def make_repo(tmp: Path, policy=True) -> Path:
    (tmp / "schemas").mkdir()
    shutil.copy(ROOT / "schemas" / "task_packet.v3.schema.json", tmp / "schemas")
    for d in ("task_queue", "processed", "icarus/runs"):
        (tmp / d).mkdir(parents=True)
        (tmp / d / ".gitkeep").write_text("")
    for f in FILES:
        if f == "ingress_policy.json" and not policy:
            continue
        shutil.copy(ROOT / f, tmp)
    for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"]):
        subprocess.run(["git", *args], cwd=tmp, check=True, capture_output=True)
    return tmp


def load_runner(tmp: Path):
    spec = importlib.util.spec_from_file_location("task_runner_t", tmp / "task_runner.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


WRITE = ("import os;os.makedirs('icarus/runs/artifacts/t',exist_ok=True);"
         "open('icarus/runs/artifacts/t/out.txt','w').write('hello')")


def packet(tid="T-RUN-001", cmd=None, outputs=None, scope="REPOSITORY_BRANCH_ONLY", executor="unittest", extra=None, limit=3):
    p = {
        "template_version": "v3.0.0", "task_id": tid, "title": "t", "objective": "o", "proposed_by": "test",
        "assigned_executor": executor, "authority_scope": scope,
        "stages": [{"stage_id": "S1", "name": "s1", "command": cmd or ["python3", "-c", WRITE],
                    "expected_outputs": outputs if outputs is not None else ["icarus/runs/artifacts/t/out.txt"],
                    "attempt_limit": limit, "timeout_seconds": 30}],
        "adjudication": {"verifier_tier": "TIER_1_MACHINE"},
        "acceptance_criteria": {"success_condition": "x", "verification_file": "icarus/runs/RUN_LOG.jsonl"},
    }
    if extra:
        p.update(extra)
    return p


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for k in ("GITHUB_TOKEN", "GITHUB_REPOSITORY", "GITHUB_SHA"):
            os.environ.pop(k, None)
        make_repo(self.tmp)
        self.mod = load_runner(self.tmp)
        self.r = self.mod.Runner(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def put(self, pkt, name="p.json"):
        f = self.tmp / "task_queue" / name
        f.write_text(pkt if isinstance(pkt, str) else json.dumps(pkt))
        return f

    def ledger(self):
        p = self.tmp / "icarus/runs/RUN_LOG.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def states(self):
        return {json.loads(f.read_text())["task_id"]: json.loads(f.read_text()) for f in (self.tmp / "state").glob("*.json")}


class LifecycleTests(Base):
    def test_full_lifecycle_reaches_complete_with_terminal_receipt(self):
        self.put(packet())
        out = self.r.once()
        self.assertEqual(out["processed"], [{"task_id": "T-RUN-001", "state": "COMPLETE"}])
        st = self.states()["T-RUN-001"]
        self.assertEqual([h["to"] for h in st["history"]],
                         ["VALIDATED", "CLAIMED", "EXECUTING", "VERIFYING", "COMPLETE"])
        self.assertEqual((st["attempts"], st["exit_status"]), (1, 0))
        self.assertRegex(st["source_sha"], r"^[0-9a-f]{40}$")
        self.assertTrue(st["owner"].startswith("task_runner@"))
        self.assertTrue(st["started_at"] and st["ended_at"])
        self.assertTrue(all(st["gate_verdict"]["checks"].values()), st["gate_verdict"])
        kinds = [l["schema"] for l in self.ledger()]
        self.assertEqual(kinds, ["icarus/receipt.v3", "icarus/terminal.v3"])
        self.assertTrue(self.r.h.verify_ledger()["ok"])
        self.assertFalse(list((self.tmp / "task_queue").glob("*.json")))
        self.assertFalse((self.tmp / "state" / "T-RUN-001.claim").exists())
        self.assertTrue((self.tmp / st["log_path"]).is_file())
        self.assertEqual(self.r.gate.audit(self.tmp)["ok"], True)

    def test_same_bytes_are_not_rerun(self):
        self.put(packet(cmd=["python3", "-c", "import sys;sys.exit(3)"]))
        self.r.once()
        self.put(packet(cmd=["python3", "-c", "import sys;sys.exit(3)"]), "again.json")
        out = self.r.once()
        self.assertEqual(len([l for l in self.ledger() if l["schema"] == "icarus/receipt.v3"]), 1)
        self.assertEqual(out["processed"][0]["state"], "FAILED")

    def test_poll_loop_picks_up_a_packet_dropped_later(self):
        self.assertEqual(self.r.once()["processed"], [])
        self.put(packet("T-LATE-001"))
        self.assertEqual(self.r.once()["processed"][0]["state"], "COMPLETE")


class IngressRejectionTests(Base):
    def assertRejected(self, raw, needle):
        before_outputs = list((self.tmp / "icarus/runs/artifacts").rglob("*")) if (self.tmp / "icarus/runs/artifacts").exists() else []
        self.put(raw)
        out = self.r.once()
        self.assertEqual(out["processed"][0]["state"], "REJECTED", out)
        rej = [l for l in self.ledger() if l["schema"] == "icarus/rejection.v3"]
        self.assertEqual(len(rej), 1)
        self.assertEqual(rej[0]["status"], "REJECTED")
        self.assertIn(needle, " | ".join(rej[0]["errors"]))
        self.assertFalse([l for l in self.ledger() if l["schema"] in ("icarus/receipt.v3", "icarus/terminal.v3")])
        self.assertFalse(list((self.tmp / "icarus/runs/artifacts").rglob("*.txt")) if (self.tmp / "icarus/runs/artifacts").exists() else False)
        self.assertEqual(before_outputs, [])
        self.assertTrue(self.r.h.verify_ledger()["ok"])
        self.assertFalse(list((self.tmp / "task_queue").glob("*.json")))
        self.assertFalse([s for s in self.states().values() if s["state"] in ("CLAIMED", "EXECUTING", "COMPLETE")])

    def test_not_json(self):
        self.assertRejected("{not json", "not valid JSON")

    def test_missing_required_field(self):
        p = packet(); del p["objective"]
        self.assertRejected(p, "objective")

    def test_additional_property(self):
        self.assertRejected(packet(extra={"surprise": 1}), "additional property")

    def test_missing_authority_scope_is_never_inferred(self):
        p = packet(); del p["authority_scope"]
        self.assertRejected(p, "authority_scope missing")

    def test_unauthorized_scope(self):
        self.assertRejected(packet(scope="FULL_PRODUCTION_ACCESS"), "not authorized")

    def test_unauthorized_executor(self):
        self.assertRejected(packet(executor="rogue-agent"), "assigned_executor")

    def test_secret_in_packet(self):
        tok = "ghp_" + "A" * 36
        self.assertRejected(packet(extra={"objective": f"use {tok}"}), "secret")

    def test_non_python_command(self):
        self.assertRejected(packet(cmd=["bash", "-c", "echo hi"]), "not allowed")

    def test_negative_constraint_pre_veto(self):
        p = packet(extra={"negative_constraints": [{"id": "NC1", "description": "d", "forbidden_patterns": ["hello"]}]})
        self.assertRejected(p, "NC1")

    def test_attempt_limit_above_three(self):
        self.assertRejected(packet(limit=4), "maximum")

    def test_missing_policy_rejects_everything(self):
        shutil.rmtree(self.tmp)
        self.tmp = Path(tempfile.mkdtemp())
        make_repo(self.tmp, policy=False)
        self.r = load_runner(self.tmp).Runner(self.tmp)
        self.assertRejected(packet(), "ingress_policy.json")


class CompletionGateNegativeTests(Base):
    def complete(self):
        self.put(packet())
        self.r.once()
        return self.states()["T-RUN-001"]

    def test_failed_stage_cannot_complete(self):
        self.put(packet(cmd=["python3", "-c", "import sys;sys.exit(2)"]))
        out = self.r.once()
        self.assertEqual(out["processed"][0]["state"], "FAILED")
        self.assertFalse([l for l in self.ledger() if l["schema"] == "icarus/terminal.v3"])
        self.assertNotEqual(self.states()["T-RUN-001"]["exit_status"], 0)

    def test_missing_output_cannot_complete(self):
        self.put(packet(cmd=["python3", "-c", "print('no file')"]))
        self.assertNotEqual(self.r.once()["processed"][0]["state"], "COMPLETE")

    def test_transition_to_complete_requires_gate(self):
        self.put(packet(cmd=["python3", "-c", "import sys;sys.exit(2)"]))
        self.r.once()
        st = self.states()["T-RUN-001"]
        st["state"] = "VERIFYING"
        with self.assertRaises(RuntimeError):
            self.r.transition(st, "COMPLETE", "forced")
        with self.assertRaises(RuntimeError):
            self.r.transition(dict(st, state="FAILED"), "COMPLETE", "illegal", _gate_ok=True)

    def test_tampered_output_fails_gate(self):
        st = self.complete()
        (self.tmp / "icarus/runs/artifacts/t/out.txt").write_text("tampered")
        v = self.r.gate.verify_completion(self.tmp, st, self.r.h)
        self.assertFalse(v["ok"]); self.assertFalse(v["checks"]["outputs_exist_and_rehash"])
        self.assertEqual(self.r.gate.audit(self.tmp)["ok"], False)

    def test_forged_exit_status_fails_gate(self):
        st = self.complete(); st["exit_status"] = 1
        self.assertFalse(self.r.gate.verify_completion(self.tmp, st, self.r.h)["checks"]["recorded_exit_status_zero"])

    def test_missing_git_sha_fails_gate(self):
        st = self.complete(); st["source_sha"] = ""
        self.assertFalse(self.r.gate.verify_completion(self.tmp, st, self.r.h)["checks"]["git_sha_recorded"])

    def test_attempts_over_cap_fails_gate(self):
        st = self.complete(); st["attempts"] = 4
        self.assertFalse(self.r.gate.verify_completion(self.tmp, st, self.r.h)["checks"]["attempts_within_cap"])

    def test_secret_in_output_fails_gate(self):
        st = self.complete()
        (self.tmp / "icarus/runs/artifacts/t/out.txt").write_text("ghp_" + "B" * 36)
        self.assertFalse(self.r.gate.verify_completion(self.tmp, st, self.r.h)["checks"]["zero_secrets_in_outputs"])

    def test_hand_edited_complete_state_is_caught_by_audit(self):
        self.put(packet(cmd=["python3", "-c", "import sys;sys.exit(2)"]))
        self.r.once()
        p = self.tmp / "state" / "T-RUN-001.json"
        st = json.loads(p.read_text()); st["state"] = "COMPLETE"; st["exit_status"] = 0
        p.write_text(json.dumps(st))
        a = self.r.gate.audit(self.tmp)
        self.assertFalse(a["ok"])
        cp = subprocess.run([sys.executable, str(self.tmp / "completion_gate.py"), "--audit"],
                            cwd=self.tmp, env=dict(os.environ, ICARUS_REPO_ROOT=str(self.tmp)), capture_output=True, text=True)
        self.assertEqual(cp.returncode, 1)

    def test_tampered_ledger_blocks_gate_and_new_runs(self):
        st = self.complete()
        lp = self.tmp / "icarus/runs/RUN_LOG.jsonl"
        lp.write_text(lp.read_text().replace('"PASS"', '"FAIL"', 1))
        self.assertFalse(self.r.gate.verify_completion(self.tmp, st, self.r.h)["checks"]["ledger_chain_valid"])


class RecoveryTests(Base):
    SLOW = ("import os,time,json;os.makedirs('icarus/runs/artifacts/rec',exist_ok=True);"
            "m='icarus/runs/artifacts/rec/marker'\n"
            "if not os.path.exists(m):\n"
            "    open(m,'w').write('1');time.sleep(120)\n"
            "open('icarus/runs/artifacts/rec/out.json','w').write(json.dumps({'ok':True}))")

    def test_kill_mid_run_then_restart_recovers_and_completes(self):
        self.put(packet("T-REC-001", cmd=["python3", "-c", self.SLOW], outputs=["icarus/runs/artifacts/rec/out.json"]))
        env = dict(os.environ, ICARUS_REPO_ROOT=str(self.tmp))
        p1 = subprocess.Popen([sys.executable, str(self.tmp / "task_runner.py"), "--once"], cwd=self.tmp, env=env,
                              start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        sp = self.tmp / "state" / "T-REC-001.json"
        deadline = time.time() + 20
        while time.time() < deadline:
            if sp.exists() and json.loads(sp.read_text()).get("state") == "EXECUTING" \
                    and (self.tmp / "icarus/runs/artifacts/rec/marker").exists():
                break
            time.sleep(0.1)
        else:
            os.killpg(p1.pid, signal.SIGKILL); p1.wait()
            self.fail("runner never reached EXECUTING")
        os.killpg(p1.pid, signal.SIGKILL)
        p1.wait()
        mid = json.loads(sp.read_text())
        self.assertEqual((mid["state"], mid["attempts"]), ("EXECUTING", 1))
        self.assertTrue(list((self.tmp / "task_queue").glob("*.json")), "packet must survive the crash")
        self.assertFalse([l for l in self.ledger() if l["schema"] == "icarus/terminal.v3"])
        p2 = subprocess.run([sys.executable, str(self.tmp / "task_runner.py"), "--once"], cwd=self.tmp, env=env,
                            capture_output=True, text=True, timeout=120)
        self.assertEqual(p2.returncode, 0, p2.stdout + p2.stderr)
        end = json.loads(sp.read_text())
        self.assertEqual(end["state"], "COMPLETE")
        self.assertEqual(end["attempts"], 2)
        trail = [h["to"] for h in end["history"]]
        self.assertIn("INTERRUPTED", trail)
        self.assertEqual(trail[-1], "COMPLETE")
        self.assertTrue(self.r.h.verify_ledger()["ok"])
        self.assertTrue(self.r.gate.audit(self.tmp)["ok"])

    def test_interruption_at_attempt_cap_blocks_instead_of_rerunning(self):
        import hashlib
        f = self.put(packet("T-CAP-001"))
        st = {"task_id": "T-CAP-001", "packet_file": "p.json", "packet_path": "task_queue/p.json",
              "packet_sha256": hashlib.sha256(f.read_bytes()).hexdigest(), "state": "EXECUTING", "owner": "dead", "attempts": 3, "history": [],
              "started_at": "t", "ended_at": None, "exit_status": None, "lease_pid": 999999, "lease_expires_epoch": 0}
        self.r.save_state(st)
        self.assertEqual(self.r.recover(), ["T-CAP-001"])
        self.assertEqual(self.states()["T-CAP-001"]["state"], "BLOCKED")
        self.assertEqual(self.r.process(self.tmp / "task_queue" / "p.json")["state"], "BLOCKED")
        self.assertFalse(self.ledger())

    def test_live_owner_is_not_taken_over(self):
        self.put(packet("T-LIVE-001"))
        st = {"task_id": "T-LIVE-001", "packet_file": "p.json", "packet_path": "task_queue/p.json",
              "packet_sha256": "x", "state": "EXECUTING", "owner": "me", "attempts": 1, "history": [],
              "started_at": "t", "ended_at": None, "exit_status": None, "lease_pid": os.getpid(),
              "lease_expires_epoch": time.time() + 300}
        self.r.save_state(st)
        self.assertEqual(self.r.recover(), [])
        self.assertEqual(self.r.process(self.tmp / "task_queue" / "p.json")["state"], "EXECUTING")
        self.assertFalse(self.ledger())

    def test_attempt_cap_holds_across_changed_packets(self):
        for i in range(3):
            self.put(packet("T-CHG-001", cmd=["python3", "-c", f"import sys;sys.exit({i + 2})"]), f"v{i}.json")
            self.assertEqual(self.r.once()["processed"][0]["state"], "FAILED")
        self.put(packet("T-CHG-001", cmd=["python3", "-c", WRITE]), "v3.json")
        self.assertEqual(self.r.once()["processed"][0]["state"], "BLOCKED")
        self.assertEqual(len([l for l in self.ledger() if l["schema"] == "icarus/receipt.v3"]), 3)

    def test_illegal_transition_rejected(self):
        st = {"task_id": "T-X-001", "state": "REJECTED", "history": []}
        with self.assertRaises(RuntimeError):
            self.r.transition(st, "CLAIMED")


if __name__ == "__main__":
    unittest.main()
