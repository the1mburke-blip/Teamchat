import json
import os
import tempfile
import unittest

from icarus.agent.governed import GovernedCore, GovernedKernel, Preflight
from icarus.agent.kernel import Grant
from icarus.agent.memory import Memory
from icarus.agent.pilot.harnesshand import HarnessHand
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
        self.mem = Memory(self.root)
        self.kernel = GovernedKernel(os.path.join(self.root, "decisions.jsonl"), self.root)

    def tearDown(self):
        self.td.cleanup()

    def grant(self, tools, **kw):
        return Grant("t1", frozenset(tools), **kw)

    def pf(self, **kw):
        base = dict(endpoint="harness-hand", token_cost="~1k", monetary_cost=0, owner="icarus", effort="low",
                    pass_evidence=({"kind": "file_exists", "path": "icarus/memory/identity.md"},),
                    blockers=(), target="wiring-test", authority_ref="owner-ok")
        base.update(kw)
        return Preflight(**base)


class TestHarnessHandUnit(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = self.td.name
        self.hh = HarnessHand(self.root, env={}, which=lambda b: None)

    def tearDown(self):
        self.td.cleanup()

    def test_probe_harness_returns_structure_no_secret_values(self):
        marker = "VALUE-" + "Q" * 12
        os.makedirs(os.path.join(self.root, ".claude"))
        with open(os.path.join(self.root, ".claude/settings.json"), "w") as f:
            f.write(json.dumps({"base_url": marker, "hooks": {}}))
        r = self.hh.execute("probe_harness", {})
        self.assertTrue(r["ok"])
        self.assertNotIn(marker, json.dumps(r))
        self.assertIn("model_slot", r["surfaces"])

    def test_write_file_and_run_tool_round_trip(self):
        self.hh.execute("write_file", {"path": "t.py", "content": "print('ok')"})
        r = self.hh.execute("run_tool", {"path": "t.py", "interpreter": "python3"})
        self.assertTrue(r["ok"])
        self.assertIn("ok", r["stdout"])

    def test_read_file_and_list_dir_delegate_to_local_files_hand(self):
        os.makedirs(os.path.join(self.root, "sub"))
        with open(os.path.join(self.root, "sub/n.txt"), "w") as f:
            f.write("hi")
        r = self.hh.execute("read_file", {"path": "sub/n.txt"})
        self.assertEqual(r["content"], "hi")
        r2 = self.hh.execute("list_dir", {"path": "sub"})
        self.assertIn("n.txt", r2["entries"])

    def test_run_tool_cannot_run_a_file_written_via_the_files_path(self):
        # even though read/write both route through this hand, run_tool's "did I write it" check is the
        # builder's own tracking, so a file dropped on disk any other way still can't be run.
        with open(os.path.join(self.root, "outside.py"), "w") as f:
            f.write("print('nope')")
        r = self.hh.execute("run_tool", {"path": "outside.py", "interpreter": "python3"})
        self.assertFalse(r["ok"])

    def test_unknown_tool(self):
        self.assertEqual(self.hh.execute("delete_everything", {})["error"], "unknown tool")


class TestWiredIntoGovernedCore(Base):
    def test_full_loop_probe_then_build_then_run_then_finish(self):
        os.makedirs(os.path.join(self.root, ".claude"))
        with open(os.path.join(self.root, ".claude/settings.json"), "w") as f:
            f.write(json.dumps({"mcpServers": {"x": {}}}))
        hh = HarnessHand(self.root, env={}, which=lambda b: None)
        steps = [
            j(action="tool", tool="probe_harness", args={}),
            j(action="tool", tool="write_file", args={"path": "tools/register.py", "content": "print('registered')"}),
            j(action="tool", tool="run_tool", args={"path": "tools/register.py", "interpreter": "python3"}),
            j(action="finish", claim="probed the harness and built a tool for it", evidence=[]),
        ]
        reasoner = ScriptedReasoner(steps)
        core = GovernedCore(self.mem, reasoner, self.kernel, hh)
        grant = self.grant(("probe_harness", "write_file", "run_tool", "read_file", "list_dir"))
        r = core.run("probe the harness and build a tool for what it finds", grant, self.pf())
        self.assertEqual(r.status, "PASS")
        self.assertEqual([t for t, _a in hh.executed], ["probe_harness", "write_file", "run_tool"])
        self.assertEqual(hh.last_probe.harness, "claude-code")
        self.assertTrue(self.kernel.verify_log())

    def test_probe_harness_denied_when_not_granted(self):
        hh = HarnessHand(self.root, env={}, which=lambda b: None)
        steps = [j(action="tool", tool="probe_harness", args={}), j(action="finish", claim="x", evidence=[])]
        reasoner = ScriptedReasoner(steps)
        core = GovernedCore(self.mem, reasoner, self.kernel, hh)
        core.run("t", self.grant(("read_file",)), self.pf())
        self.assertEqual(hh.executed, [])

    def test_write_file_inside_wiring_still_respects_protected_paths(self):
        hh = HarnessHand(self.root, env={}, which=lambda b: None)
        steps = [j(action="tool", tool="write_file", args={"path": "icarus/agent/x.py", "content": "y"}),
                 j(action="finish", claim="x", evidence=[])]
        reasoner = ScriptedReasoner(steps)
        core = GovernedCore(self.mem, reasoner, self.kernel, hh)
        core.run("t", self.grant(("write_file",)), self.pf())
        self.assertFalse(os.path.isfile(os.path.join(self.root, "icarus/agent/x.py")))


if __name__ == "__main__":
    unittest.main()
