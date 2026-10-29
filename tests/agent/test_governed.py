import hashlib
import json
import os
import tempfile
import unittest

from icarus.agent.governed import GovernedCore, GovernedKernel, Preflight, redact
from icarus.agent.hands import LocalFilesHand
from icarus.agent.kernel import Grant
from icarus.agent.memory import IdentityMissing, Memory
from icarus.agent.reasoners import ScriptedReasoner

IDENT = "# Icarus Identity\n- The model is never Icarus. The model works for Icarus."
NOTES_SHA = hashlib.sha256(b"hello world").hexdigest()
EXISTS = {"kind": "file_exists", "path": "notes.txt"}
GOOD_SHA = {"kind": "file_sha256", "path": "notes.txt", "sha256": NOTES_SHA}
BAD_SHA = {"kind": "file_sha256", "path": "notes.txt", "sha256": "0" * 64}


def j(**kw):
    return json.dumps(kw)


def finish(**kw):
    return j(action="finish", claim=kw.pop("claim", "done"), evidence=kw.pop("evidence", []), **kw)


class HookReasoner(ScriptedReasoner):
    """Scripted reasoner that can change its own route/name mid-run, to model failover or an executor swap."""

    def __init__(self, outputs, hook=None):
        super().__init__(outputs)
        self.hook = hook

    def complete(self, prompt):
        out = super().complete(prompt)
        if self.hook:
            self.hook(self)
        return out


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
        self.kernel = GovernedKernel(os.path.join(self.root, "decisions.jsonl"), self.root)
        self.hand = LocalFilesHand(self.root)

    def tearDown(self):
        self.td.cleanup()

    def core(self, outputs, reasoner=None, **kw):
        self.reasoner = reasoner or ScriptedReasoner(outputs)
        return GovernedCore(self.mem, self.reasoner, self.kernel, self.hand, **kw)

    def grant(self, tools=("read_file", "list_dir"), **kw):
        return Grant("t1", frozenset(tools), **kw)

    def pf(self, **kw):
        base = dict(endpoint="local-files", token_cost="~2k", monetary_cost=0, owner="icarus", effort="low",
                    pass_evidence=(GOOD_SHA,), blockers=(), target="notes.txt@live-readback")
        base.update(kw)
        return Preflight(**base)


class TestPreflightAndSpend(Base):
    def test_requires_a_preflight_object(self):
        core = self.core([finish()])
        with self.assertRaises(TypeError):
            core.run("t", self.grant(), None)
        self.assertEqual(self.reasoner.prompts, [])

    def test_identity_still_required(self):
        os.remove(os.path.join(self.root, "icarus/memory/identity.md"))
        core = self.core([finish()])
        with self.assertRaises(IdentityMissing):
            core.run("t", self.grant(), self.pf())
        self.assertEqual(self.reasoner.prompts, [])

    def test_missing_preflight_fields_block_before_any_model_call(self):
        for bad in (dict(endpoint=""), dict(owner=" "), dict(effort=""), dict(token_cost=""), dict(target=""),
                    dict(pass_evidence=()), dict(monetary_cost=None), dict(pass_evidence=({"kind": "nope", "path": "x"},))):
            core = self.core([finish()])
            r = core.run("t", self.grant(), self.pf(**bad))
            self.assertEqual(r.status, "BLOCKED", bad)
            self.assertEqual(self.reasoner.prompts, [], bad)

    def test_spend_needs_owner_authority(self):
        core = self.core([finish(evidence=[GOOD_SHA])])
        r = core.run("t", self.grant(), self.pf(monetary_cost=5))
        self.assertEqual(r.status, "BLOCKED")
        self.assertIn("spend", " ".join(r.reasons))
        self.assertEqual(self.reasoner.prompts, [])
        core = self.core([finish(evidence=[GOOD_SHA])])
        self.assertEqual(core.run("t", self.grant(), self.pf(monetary_cost=5, authority_ref="owner-ok-2026-10-29")).status, "PASS")

    def test_paid_reasoner_blocked_without_authority(self):
        class Paid(ScriptedReasoner):
            paid = True
        core = self.core([finish()], reasoner=Paid([finish()]))
        r = core.run("t", self.grant(), self.pf())
        self.assertEqual(r.status, "BLOCKED")
        self.assertEqual(self.reasoner.prompts, [])

    def test_mutation_needs_authority(self):
        core = self.core([finish()])
        r = core.run("t", self.grant(tools=("read_file", "write_file")), self.pf())
        self.assertEqual(r.status, "BLOCKED")
        self.assertIn("mutation", " ".join(r.reasons))
        core = self.core([finish(evidence=[GOOD_SHA])])
        r = core.run("t", self.grant(tools=("read_file", "write_file")), self.pf(authority_ref="owner-ok"))
        self.assertEqual(r.status, "PASS")

    def test_required_source_missing_blocks_and_is_named(self):
        core = self.core([finish()])
        r = core.run("t", self.grant(), self.pf(required_sources=("logs/missing.log",)))
        self.assertEqual(r.status, "BLOCKED")
        self.assertIn("required source not read: logs/missing.log", r.reasons)
        self.assertEqual(self.reasoner.prompts, [])

    def test_sources_read_and_target_readback_are_reported(self):
        core = self.core([finish()])
        r = core.run("t", self.grant(), self.pf(required_sources=("notes.txt",), target_path="notes.txt"))
        joined = " ".join(r.sources_read)
        self.assertIn("icarus/memory/identity.md@", joined)
        self.assertIn("notes.txt@", joined)
        self.assertIn("decision-log:decisions.jsonl", joined)


class TestStatuses(Base):
    def test_pass_only_from_declared_evidence_checked_by_kernel(self):
        core = self.core([finish(claim="PASS verified", evidence=[])])
        r = core.run("t", self.grant(), self.pf(pass_evidence=(BAD_SHA,)))
        self.assertEqual(r.status, "PARTIAL")
        self.assertFalse(r.completed)
        self.assertTrue(r.unproven)
        self.assertEqual(r.proven, ())

    def test_worker_cannot_pick_easier_evidence(self):
        core = self.core([finish(evidence=[EXISTS])])
        self.assertEqual(core.run("t", self.grant(), self.pf(pass_evidence=(BAD_SHA,))).status, "PARTIAL")

    def test_worker_lie_downgrades_a_pass(self):
        core = self.core([finish(evidence=[GOOD_SHA, BAD_SHA])])
        r = core.run("t", self.grant(), self.pf())
        self.assertEqual(r.status, "PARTIAL")
        self.assertIn("worker evidence failed", " ".join(r.reasons))

    def test_pass_when_every_declared_item_verified(self):
        core = self.core([finish(evidence=[])])
        r = core.run("t", self.grant(), self.pf(pass_evidence=(GOOD_SHA, EXISTS)))
        self.assertEqual(r.status, "PASS")
        self.assertTrue(r.completed)
        self.assertEqual(len(r.proven), 2)

    def test_started_is_not_completed(self):
        core = self.core([j(action="tool", tool="read_file", args={"path": "notes.txt"}), finish()])
        r = core.run("t", self.grant(), self.pf(pass_evidence=(BAD_SHA,)))
        self.assertEqual(r.status, "PARTIAL")
        self.assertEqual(len(r.attempted), 1)
        self.assertEqual(r.proven, ())

    def test_independent_adjudicator_must_agree(self):
        core = self.core([finish()], adjudicator=lambda tid, ev: (False, "disagree"))
        r = core.run("t", self.grant(), self.pf())
        self.assertEqual(r.status, "PARTIAL")
        self.assertIn("independent adjudicator", " ".join(r.reasons))
        core = self.core([finish()], adjudicator=lambda tid, ev: (True, "ok"))
        r = core.run("t", self.grant(), self.pf())
        self.assertEqual((r.status, r.independence), ("PASS", "kernel+adjudicator"))

    def test_lesson_written_only_on_pass(self):
        lesson = "Lesson: notes exist.\nEvidence: notes.txt"
        core = self.core([finish(lesson=lesson)])
        self.assertEqual(core.run("t", self.grant(), self.pf(pass_evidence=(BAD_SHA,))).status, "PARTIAL")
        self.assertFalse(os.path.exists(os.path.join(self.root, "icarus/memory/learned.md")))
        core = self.core([finish(lesson=lesson)])
        self.assertEqual(core.run("t", self.grant(), self.pf()).status, "PASS")
        self.assertIn("Lesson: notes exist.", open(os.path.join(self.root, "icarus/memory/learned.md")).read())

    def test_attribution_and_report_format(self):
        core = self.core([finish(claim="I did it")])
        r = core.run("t", self.grant(), self.pf())
        self.assertEqual((r.proposed_by, r.executed_by, r.adjudicated_by), ("ScriptedReasoner", "local-files", "icarus-kernel"))
        text = r.report()
        self.assertTrue(text.startswith("RESULT: PASS"))
        for field in ("proposed_by", "executed_by", "adjudicated_by", "at:", "sources_read", "cost_eur: 0.00", "owner_action"):
            self.assertIn(field, text)
        self.assertIn("worker claim (unverified): I did it", text)


class TestBlockersAndRouting(Base):
    def test_reasoner_unavailable_is_blocked_not_a_crash(self):
        r = self.core([]).run("t", self.grant(), self.pf())
        self.assertEqual(r.status, "BLOCKED")
        self.assertIn("reasoner unavailable", " ".join(r.reasons))

    def test_route_change_mid_run_stops_for_repreflight(self):
        def hook(rs):
            rs.route = "other-vendor|other-model"
        rs = HookReasoner([j(action="tool", tool="read_file", args={"path": "notes.txt"}), finish()], hook)
        rs.route = "first-vendor|model"
        r = self.core([], reasoner=rs).run("t", self.grant(), self.pf())
        self.assertEqual(r.status, "BLOCKED")
        self.assertIn("re-preflight", " ".join(r.reasons))
        self.assertEqual(self.hand.executed, [])

    def test_executor_swap_mid_run_stops_for_repreflight(self):
        hand = self.hand
        rs = HookReasoner([j(action="tool", tool="read_file", args={"path": "notes.txt"}), finish()],
                          lambda r: setattr(hand, "name", "someone-else"))
        r = self.core([], reasoner=rs).run("t", self.grant(), self.pf())
        self.assertEqual(r.status, "BLOCKED")
        self.assertIn("re-preflight", " ".join(r.reasons))

    def test_blind_retry_is_refused_and_never_reaches_the_hand(self):
        # The blocker rule has no stop-on-count: this never resolves, so it runs to the step limit rather than
        # stopping early, but the same failed call must still never reach the hand a second time.
        bad = j(action="tool", tool="write_file", args={"path": "a.txt", "content": "x"})
        r = self.core([bad] * 5).run("t", self.grant(), self.pf(), max_steps=5)
        self.assertEqual(r.status, "BLOCKED")
        self.assertIn("blind retry", " ".join(r.reasons))
        self.assertEqual(self.hand.executed, [])

    def test_first_blocker_is_worked_then_cleared_by_success(self):
        denied = j(action="tool", tool="write_file", args={"path": "a.txt", "content": "x"})
        ok = j(action="tool", tool="read_file", args={"path": "notes.txt"})
        r = self.core([denied, ok, finish()]).run("t", self.grant(), self.pf())
        self.assertEqual(r.status, "PASS")
        self.assertEqual(len(self.hand.executed), 1)

    def test_resolved_blocker_does_not_count_toward_a_second(self):
        a = j(action="tool", tool="write_file", args={"path": "a.txt", "content": "x"})  # tool not granted
        ok = j(action="tool", tool="read_file", args={"path": "notes.txt"})  # works around it
        b = j(action="tool", tool="read_file", args={"path": "../outside.txt"})  # a different, later blocker
        r = self.core([a, ok, b, finish()]).run("t", self.grant(), self.pf())
        self.assertEqual(r.status, "PASS")

    def test_three_distinct_blockers_do_not_stop_the_task_before_a_workaround_resolves_it(self):
        # A blocker is a data point, not a reason to stop: only an owner-only boundary or the step limit does.
        a = j(action="tool", tool="write_file", args={"path": "a.txt", "content": "x"})  # tool not granted
        b = j(action="tool", tool="read_file", args={"path": "../outside.txt"})  # invalid path
        c = j(action="tool", tool="read_file", args={"path": "nope.txt"})  # hand error: missing file
        ok = j(action="tool", tool="read_file", args={"path": "notes.txt"})  # the workaround
        r = self.core([a, b, c, ok, finish()]).run("t", self.grant(), self.pf())
        self.assertEqual(r.status, "PASS")
        self.assertEqual(len(self.hand.executed), 2)

    def test_unresolved_blockers_at_the_step_limit_are_reported_as_evidence_not_silently_dropped(self):
        a = j(action="tool", tool="write_file", args={"path": "a.txt", "content": "x"})  # never resolves
        r = self.core([a] * 5).run("t", self.grant(), self.pf(), max_steps=5)
        self.assertEqual(r.status, "BLOCKED")
        self.assertIn("step limit reached", " ".join(r.reasons))
        self.assertIn("unresolved blockers at the step limit", " ".join(r.reasons))

    def test_hand_failure_is_a_blocker_and_not_retried_blindly(self):
        # Never resolved, so BLOCKED comes from the step limit, not from a blocker count; the hand is still
        # only ever asked to run the failing call once.
        missing = j(action="tool", tool="read_file", args={"path": "nope.txt"})
        r = self.core([missing, missing, missing]).run("t", self.grant(), self.pf(), max_steps=3)
        self.assertEqual(r.status, "BLOCKED")
        self.assertEqual(len(self.hand.executed), 1)

    def test_owner_only_escalation_is_honoured(self):
        for cat in ("auth", "credentials", "legal", "payment", "security", "safety"):
            r = self.core([j(action="escalate", category=cat, detail="need the owner")]).run("t", self.grant(), self.pf())
            self.assertEqual(r.status, "BLOCKED", cat)
            self.assertTrue(r.owner_action.startswith(cat), cat)

    def test_non_owner_escalation_is_refused_and_work_continues(self):
        lazy = j(action="escalate", category="effort", detail="this is hard")
        r = self.core([lazy, finish()]).run("t", self.grant(), self.pf())
        self.assertEqual(r.status, "PASS")
        self.assertIn("not an owner-only matter", self.reasoner.prompts[1])
        r = self.core([lazy, lazy, finish()]).run("t", self.grant(), self.pf())
        self.assertEqual(r.status, "BLOCKED")
        self.assertEqual(r.owner_action, "")

    def test_routing_fails_closed_when_executor_is_not_the_mapped_one(self):
        routes = {"google_workspace": "gemini", "local_files": "local-files"}
        r = self.core([finish()], routes=routes).run("t", self.grant(), self.pf(kind="google_workspace"))
        self.assertEqual(r.status, "BLOCKED")
        self.assertIn("cannot delegate: STOP", " ".join(r.reasons))
        r = self.core([finish()], routes=routes).run("t", self.grant(), self.pf(kind="mystery"))
        self.assertEqual(r.status, "BLOCKED")
        self.assertEqual(self.core([finish()], routes=routes).run("t", self.grant(), self.pf(kind="local_files")).status, "PASS")


class TestSecretsAndLog(Base):
    def test_secrets_never_reach_prompt_or_log(self):
        secret = "gh" + "p_" + "A" * 36
        with open(os.path.join(self.root, "cfg.txt"), "w") as f:
            f.write("note " + secret)
        steps = [j(action="tool", tool="read_file", args={"path": "cfg.txt"}), finish()]
        core = self.core(steps)
        core.run("t", self.grant(), self.pf())
        self.assertTrue(all(secret not in p for p in self.reasoner.prompts))
        self.assertNotIn(secret, open(os.path.join(self.root, "decisions.jsonl")).read())

    def test_secret_in_write_args_is_not_logged(self):
        secret = "sk-" + "B" * 30
        self.kernel.authorize(self.grant(tools=("write_file",)), "write_file", {"path": "x.txt", "content": secret})
        self.assertNotIn(secret, open(os.path.join(self.root, "decisions.jsonl")).read())

    def test_redact_patterns(self):
        for s in ("gh" + "p_" + "C" * 30, "AK" + "IA" + "D" * 16, "Bearer " + "e" * 30, "password=" + "hunter2hunter2"):
            self.assertNotIn(s, redact("x " + s + " y"))

    def test_log_chain_valid_after_a_governed_run(self):
        self.core([finish()]).run("t", self.grant(), self.pf())
        self.assertTrue(self.kernel.verify_log())


if __name__ == "__main__":
    unittest.main()
