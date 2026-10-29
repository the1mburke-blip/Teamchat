"""End-to-end against a stand-in dsh harness (fixture, not the real laptop install).

Mirrors the layout from the 23 Oct laptop readback: .dsh/profiles/desktop/cordis.patch.yml with a model
provider, an mcp_servers block, and a permission_mode. No real laptop is touched; the device bridge was
unreachable when this was written, so this proves the wiring works against a realistic stand-in only.
Task #9 (the real laptop) is separate and still blocked on that connection.
"""
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
DSH_PATCH = (
    "model_provider: openrouter\n"
    "base_url: https://openrouter.ai/api/v1\n"
    "mcp_servers:\n"
    "  icarus-gate:\n"
    "    command: node\n"
    '    args: ["r6/gate.mjs"]\n'
    "permission_mode: ask\n"
)


def j(**kw):
    return json.dumps(kw)


class TestPilotAgainstDshFixture(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = self.td.name
        os.makedirs(os.path.join(self.root, "icarus/memory"))
        with open(os.path.join(self.root, "icarus/memory/identity.md"), "w") as f:
            f.write(IDENT)
        os.makedirs(os.path.join(self.root, ".dsh/profiles/desktop"))
        with open(os.path.join(self.root, ".dsh/profiles/desktop/cordis.patch.yml"), "w") as f:
            f.write(DSH_PATCH)
        self.mem = Memory(self.root)
        self.kernel = GovernedKernel(os.path.join(self.root, "decisions.jsonl"), self.root)
        self.hh = HarnessHand(self.root, env={}, which=lambda b: None)

    def tearDown(self):
        self.td.cleanup()

    def grant(self, tools, **kw):
        return Grant("t1", frozenset(tools), **kw)

    def pf(self, **kw):
        base = dict(endpoint="dsh-fixture", token_cost="~1k", monetary_cost=0, owner="icarus", effort="low",
                    pass_evidence=({"kind": "file_exists", "path": ".dsh/profiles/desktop/cordis.patch.yml"},),
                    blockers=(), target="dsh fixture probe", authority_ref="owner-ok")
        base.update(kw)
        return Preflight(**base)

    def test_probe_identifies_dsh_and_all_three_surfaces_from_the_patch_file(self):
        r = self.hh.execute("probe_harness", {})
        self.assertEqual((r["ok"], r["harness"], r["status"]), (True, "dsh", "FOUND"))
        self.assertEqual({e["where"] for e in r["surfaces"]["model_slot"]}, {".dsh/profiles/desktop/cordis.patch.yml"})
        self.assertIn("base_url", {e["detail"] for e in r["surfaces"]["model_slot"]})
        self.assertEqual([e["detail"] for e in r["surfaces"]["approval_channel"]], ["permission_mode"])
        self.assertEqual([e["detail"] for e in r["surfaces"]["tool_registry"]], ["mcp_servers"])

    def test_full_run_probes_dsh_builds_a_registration_tool_and_passes(self):
        steps = [
            j(action="tool", tool="probe_harness", args={}),
            j(action="tool", tool="write_file", args={"path": "tools/register_icarus_slot.py",
                                                        "content": "print('icarus registered on model_slot+tool_registry')"}),
            j(action="tool", tool="run_tool", args={"path": "tools/register_icarus_slot.py", "interpreter": "python3"}),
            j(action="finish", claim="probed dsh, found model_slot/approval_channel/tool_registry, built the registration tool", evidence=[]),
        ]
        reasoner = ScriptedReasoner(steps)
        core = GovernedCore(self.mem, reasoner, self.kernel, self.hh)
        grant = self.grant(("probe_harness", "write_file", "run_tool", "read_file", "list_dir"))
        r = core.run("probe the harness I'm plugged into and build whatever is needed to take the model slot", grant, self.pf())
        self.assertEqual(r.status, "PASS")
        self.assertEqual(self.hh.last_probe.harness, "dsh")
        self.assertEqual(set(self.hh.last_probe.surfaces), {"model_slot", "approval_channel", "tool_registry"})
        self.assertTrue(self.kernel.verify_log())

    def test_identity_is_still_required_even_against_a_real_looking_harness(self):
        os.remove(os.path.join(self.root, "icarus/memory/identity.md"))
        from icarus.agent.memory import IdentityMissing
        core = GovernedCore(self.mem, ScriptedReasoner([j(action="finish", claim="x", evidence=[])]), self.kernel, self.hh)
        with self.assertRaises(IdentityMissing):
            core.run("t", self.grant(("probe_harness",)), self.pf())


if __name__ == "__main__":
    unittest.main()
