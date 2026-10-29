import hashlib
import json
import os
import tempfile
import unittest

from icarus.agent.core import IcarusCore, parse_proposal
from icarus.agent.hands import LocalFilesHand
from icarus.agent.kernel import Grant, Kernel
from icarus.agent.memory import IdentityMissing, Memory, MemoryRejected
from icarus.agent.reasoners import ScriptedReasoner

IDENT = "# Icarus Identity\n- The model is never Icarus. The model works for Icarus."


def j(**kw):
    return json.dumps(kw)


class Base(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = self.td.name
        os.makedirs(os.path.join(self.root, "icarus/memory"))
        with open(os.path.join(self.root, "icarus/memory/identity.md"), "w") as f:
            f.write(IDENT)
        with open(os.path.join(self.root, "notes.txt"), "w") as f:
            f.write("hello world")
        self.mem = Memory(self.root)
        self.kernel = Kernel(os.path.join(self.root, "decisions.jsonl"), self.root)
        self.hand = LocalFilesHand(self.root)

    def tearDown(self):
        self.td.cleanup()

    def core(self, outputs):
        self.reasoner = ScriptedReasoner(outputs)
        return IcarusCore(self.mem, self.reasoner, self.kernel, self.hand)

    def grant(self, tools=("read_file", "write_file", "list_dir"), **kw):
        return Grant("t1", frozenset(tools), **kw)


class TestCore(Base):
    def test_core_builds_prompt_itself(self):
        core = self.core([j(action="finish", claim="x", evidence=[{"kind": "file_exists", "path": "notes.txt"}])])
        core.run("do the thing", self.grant())
        p = self.reasoner.prompts[0]
        self.assertIn("The model is never Icarus", p)
        self.assertIn("do the thing", p)

    def test_refuses_without_identity(self):
        os.remove(os.path.join(self.root, "icarus/memory/identity.md"))
        core = self.core([j(action="finish", claim="x", evidence=[])])
        with self.assertRaises(IdentityMissing):
            core.run("t", self.grant())
        self.assertEqual(self.reasoner.prompts, [])  # model never called

    def test_denied_tool_never_reaches_hand(self):
        core = self.core([
            j(action="tool", tool="write_file", args={"path": "a.txt", "content": "x"}),
            j(action="finish", claim="x", evidence=[]),
        ])
        r = core.run("t", self.grant(tools=("read_file",)))
        self.assertEqual(self.hand.executed, [])
        self.assertEqual(r.verdict, "FAIL")
        self.assertFalse(os.path.exists(os.path.join(self.root, "a.txt")))

    def test_protected_and_escape_and_secret_paths_denied(self):
        for path in ("icarus/memory/identity.md", "../outside.txt", ".env", "icarus/agent/kernel.py", "%USERPROFILE%/x", "/etc/passwd"):
            d = self.kernel.authorize(self.grant(), "write_file", {"path": path, "content": "x"})
            self.assertFalse(d.allowed, path)

    def test_worker_cannot_self_pass(self):
        core = self.core([j(action="finish", claim="PASS, verified, done", verdict="PASS", evidence=[])])
        self.assertEqual(core.run("t", self.grant()).verdict, "FAIL")
        wrong = [{"kind": "file_sha256", "path": "notes.txt", "sha256": "0" * 64}]
        core = self.core([j(action="finish", claim="PASS", evidence=wrong)])
        self.assertEqual(core.run("t", self.grant()).verdict, "FAIL")
        good = [{"kind": "file_sha256", "path": "notes.txt", "sha256": hashlib.sha256(b"hello world").hexdigest()}]
        core = self.core([j(action="finish", claim="done", evidence=good)])
        self.assertEqual(core.run("t", self.grant()).verdict, "PASS")

    def test_budget_hard_stop(self):
        loop = [j(action="tool", tool="read_file", args={"path": "notes.txt"})] * 10
        core = self.core(loop)
        r = core.run("t", self.grant(max_calls=3))
        self.assertEqual(r.verdict, "FAIL")
        self.assertIn("budget exhausted", r.reasons)
        self.assertEqual(len(self.hand.executed), 3)

    def test_invalid_output_is_not_blind_retried(self):
        core = self.core(["no json here", "still nothing", j(action="finish", claim="x", evidence=[])])
        r = core.run("t", self.grant())
        self.assertEqual(r.verdict, "FAIL")
        self.assertEqual(len(self.reasoner.prompts), 2)  # stopped before a third call
        self.assertIn("not a valid JSON proposal", self.reasoner.prompts[1])  # second call carried new info

    def test_halt_after_repeated_denials(self):
        bad = [j(action="tool", tool="delete_file", args={"path": "x"})] * 8
        core = self.core(bad)
        r = core.run("t", self.grant(tools=("read_file",)))
        self.assertEqual(r.verdict, "FAIL")
        self.assertTrue(self.kernel.halted("t1"))

    def test_log_is_hash_chained_and_tamper_evident(self):
        core = self.core([j(action="finish", claim="x", evidence=[{"kind": "file_exists", "path": "notes.txt"}])])
        core.run("t", self.grant())
        self.assertTrue(self.kernel.verify_log())
        p = os.path.join(self.root, "decisions.jsonl")
        text = open(p).read().replace('"PASS"', '"FAIL"', 1)
        open(p, "w").write(text)
        self.assertFalse(self.kernel.verify_log())

    def test_lesson_written_only_on_pass_with_real_evidence(self):
        ev = [{"kind": "file_exists", "path": "notes.txt"}]
        lesson = "Lesson: notes exist.\nEvidence: notes.txt"
        core = self.core([j(action="finish", claim="x", evidence=ev, lesson=lesson)])
        self.assertEqual(core.run("t", self.grant()).verdict, "PASS")
        self.assertIn("Lesson: notes exist.", open(os.path.join(self.root, "icarus/memory/learned.md")).read())
        # FAIL verdict: lesson must not be written
        core = self.core([j(action="finish", claim="x", evidence=[], lesson="Lesson: nope.\nEvidence: notes.txt")])
        core.run("t", self.grant())
        self.assertNotIn("Lesson: nope.", open(os.path.join(self.root, "icarus/memory/learned.md")).read())

    def test_parse_proposal_never_executes(self):
        self.assertIsNone(parse_proposal("__import__('os').system('x')"))
        self.assertIsNone(parse_proposal('{"action":"shell","cmd":"rm -rf /"}'))
        self.assertEqual(parse_proposal('noise {"action":"finish"} trailing')["action"], "finish")


class TestMemory(Base):
    def test_write_back_rules(self):
        with self.assertRaises(MemoryRejected):
            self.mem.write_back("Lesson with no evidence")
        with self.assertRaises(MemoryRejected):
            self.mem.write_back("L\nEvidence: missing.txt")
        with self.assertRaises(MemoryRejected):
            self.mem.write_back("L\nEvidence: icarus/memory/identity.md")
        with self.assertRaises(MemoryRejected):
            self.mem.write_back("L\nEvidence: ../outside")
        self.mem.write_back("Ok lesson\nEvidence: notes.txt")

    def test_recall_ranks_relevant_lessons(self):
        with open(os.path.join(self.root, "icarus/memory/learned.md"), "w") as f:
            f.write("Gemini 503 overload needs cooldown before failover\n\nUnrelated note about shirts and mugs\n")
        out = self.mem.recall("gemini overload failover")
        self.assertIn("cooldown", out)
        self.assertNotIn("shirts", out)


if __name__ == "__main__":
    unittest.main()
