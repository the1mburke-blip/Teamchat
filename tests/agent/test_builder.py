import json
import os
import tempfile
import unittest

from icarus.agent.governed import GovernedCore, GovernedKernel, Preflight
from icarus.agent.kernel import Grant
from icarus.agent.memory import Memory
from icarus.agent.pilot.builder import ToolBuilder
from icarus.agent.reasoners import ScriptedReasoner

IDENT = "# Icarus Identity\n- The model is never Icarus. The model works for Icarus."


def j(**kw):
    return json.dumps(kw)


class TestToolBuilderUnit(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = self.td.name
        self.tb = ToolBuilder(self.root)

    def tearDown(self):
        self.td.cleanup()

    def test_write_then_run_python_tool(self):
        self.tb.execute("write_file", {"path": "tools/hello.py", "content": "print('hi from tool')"})
        r = self.tb.execute("run_tool", {"path": "tools/hello.py", "interpreter": "python3"})
        self.assertTrue(r["ok"])
        self.assertIn("hi from tool", r["stdout"])

    def test_cannot_run_a_file_it_did_not_write(self):
        full = os.path.join(self.root, "preexisting.py")
        with open(full, "w") as f:
            f.write("print('not written by the hand')")
        r = self.tb.execute("run_tool", {"path": "preexisting.py", "interpreter": "python3"})
        self.assertEqual(r, {"ok": False, "error": "run_tool only runs a file this hand wrote in this run", "origin": "rule"})

    def test_disallowed_interpreter_refused(self):
        self.tb.execute("write_file", {"path": "x.sh", "content": "echo hi"})
        r = self.tb.execute("run_tool", {"path": "x.sh", "interpreter": "bash"})
        self.assertFalse(r["ok"])
        self.assertEqual(r["origin"], "rule")

    def test_argv_must_be_string_list_not_a_shell_string(self):
        self.tb.execute("write_file", {"path": "x.py", "content": "print('ok')"})
        r = self.tb.execute("run_tool", {"path": "x.py", "interpreter": "python3", "argv": "rm -rf /"})
        self.assertFalse(r["ok"])
        self.assertEqual(r["origin"], "rule")

    def test_timeout_is_enforced(self):
        self.tb.timeout = 1
        self.tb.execute("write_file", {"path": "slow.py", "content": "import time; time.sleep(5)"})
        r = self.tb.execute("run_tool", {"path": "slow.py", "interpreter": "python3"})
        self.assertEqual(r, {"ok": False, "error": "timeout"})

    def test_invalid_path_refused(self):
        r = self.tb.execute("write_file", {"path": "../outside.py", "content": "x"})
        self.assertFalse(r["ok"])


class TestToolBuilderUnderKernel(unittest.TestCase):
    """The builder hand carries no authority of its own: the SAME kernel gates it as any other hand."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = self.td.name
        os.makedirs(os.path.join(self.root, "icarus/memory"))
        with open(os.path.join(self.root, "icarus/memory/identity.md"), "w") as f:
            f.write(IDENT)
        self.mem = Memory(self.root)
        self.kernel = GovernedKernel(os.path.join(self.root, "decisions.jsonl"), self.root)
        self.tb = ToolBuilder(self.root)

    def tearDown(self):
        self.td.cleanup()

    def grant(self, tools, **kw):
        return Grant("t1", frozenset(tools), **kw)

    def pf(self, **kw):
        base = dict(endpoint="builder", token_cost="~1k", monetary_cost=0, owner="icarus", effort="low",
                    pass_evidence=({"kind": "file_exists", "path": "icarus/memory/identity.md"},),
                    blockers=(), target="tool-build", authority_ref="owner-ok")
        base.update(kw)
        return Preflight(**base)

    def test_kernel_still_denies_writing_inside_protected_paths(self):
        d = self.kernel.authorize(self.grant(("write_file",)), "write_file", {"path": "icarus/agent/x.py", "content": "y"})
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, "protected path")

    def test_governed_core_runs_the_builder_as_a_grant_bounded_hand(self):
        steps = [
            j(action="tool", tool="write_file", args={"path": "tools/t.py", "content": "print('done')"}),
            j(action="tool", tool="run_tool", args={"path": "tools/t.py", "interpreter": "python3"}),
            j(action="finish", claim="built and ran a tool", evidence=[]),
        ]
        reasoner = ScriptedReasoner(steps)
        core = GovernedCore(self.mem, reasoner, self.kernel, self.tb)
        r = core.run("write a missing tool and run it", self.grant(("write_file", "run_tool")), self.pf())
        self.assertEqual(r.status, "PASS")
        self.assertEqual(len(self.tb.executed), 2)
        self.assertTrue(os.path.isfile(os.path.join(self.root, "tools/t.py")))

    def test_write_file_outside_grant_path_is_denied_before_it_runs(self):
        steps = [j(action="tool", tool="write_file", args={"path": "outside/t.py", "content": "print(1)"}), j(action="finish", claim="x", evidence=[])]
        reasoner = ScriptedReasoner(steps)
        core = GovernedCore(self.mem, reasoner, self.kernel, self.tb)
        core.run("t", self.grant(("write_file",), allowed_paths=("tools",)), self.pf())
        self.assertFalse(os.path.isfile(os.path.join(self.root, "outside/t.py")))


if __name__ == "__main__":
    unittest.main()
