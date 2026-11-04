import hashlib
import json
import os
import tempfile
import unittest

from icarus.agent.governed import (GovernedCore, GovernedKernel, HarnessModeViolation, NullHand, Preflight, StepOutcome,
                                   StepState)
from icarus.agent.hands import LocalFilesHand
from icarus.agent.kernel import Grant, MAX_CONSECUTIVE_DENIALS
from icarus.agent.reasoners import ReasonerUnavailable, ScriptedReasoner

IDENT = "# Icarus Identity\n- The model is never Icarus. The model works for Icarus."
NOTES_SHA = hashlib.sha256(b"hello world").hexdigest()
GOOD_SHA = {"kind": "file_sha256", "path": "notes.txt", "sha256": NOTES_SHA}
BAD_SHA = {"kind": "file_sha256", "path": "notes.txt", "sha256": "0" * 64}


def j(**kw):
    return json.dumps(kw)


def tool(name, **args):
    return j(action="tool", tool=name, args=args)


def finish(**kw):
    return j(action="finish", claim=kw.pop("claim", "done"), evidence=kw.pop("evidence", []), **kw)


class SpyHand(NullHand):
    """A NullHand that also counts anything that reaches execute, to show nothing ever does."""

    def __init__(self):
        super().__init__("harness:test")
        self.touched = 0

    def execute(self, tool, args):
        self.touched += 1
        return super().execute(tool, args)


class Base(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = self.td.name
        os.makedirs(os.path.join(self.root, "icarus/memory"))
        with open(os.path.join(self.root, "icarus/memory/identity.md"), "w") as f:
            f.write(IDENT)
        with open(os.path.join(self.root, "notes.txt"), "w") as f:
            f.write("hello world")
        from icarus.agent.memory import Memory
        self.mem = Memory(self.root)
        self.kernel = GovernedKernel(os.path.join(self.root, "decisions.jsonl"), self.root)
        self.hand = SpyHand()

    def tearDown(self):
        self.td.cleanup()

    def core(self, outputs, **kw):
        self.reasoner = ScriptedReasoner(outputs)
        return GovernedCore(self.mem, self.reasoner, self.kernel, self.hand, **kw)

    def grant(self, tools=("read_file", "list_dir"), **kw):
        return Grant("t1", frozenset(tools), **kw)

    def pf(self, **kw):
        base = dict(endpoint="harness:test", token_cost="~2k", monetary_cost=0, owner="icarus", effort="low",
                    pass_evidence=(GOOD_SHA,), blockers=(), target="notes.txt@live-readback")
        base.update(kw)
        return Preflight(**base)

    def begin(self, core, **kw):
        return core.begin("read the notes", self.grant(**kw), self.pf())

    def kernel_log(self):
        if not os.path.exists(self.kernel.log_path):
            return []
        with open(self.kernel.log_path) as f:
            return [json.loads(line)["body"]["event"] for line in f if line.strip()]


class TestNullHand(Base):
    def test_it_cannot_execute_and_the_violation_is_not_swallowable(self):
        h = NullHand("harness:dsh")
        self.assertEqual(h.tools(), {})
        self.assertEqual(h.probe()["name"], "harness:dsh")
        self.assertFalse(h.paid)
        with self.assertRaises(HarnessModeViolation):
            h.execute("read_file", {"path": "notes.txt"})
        self.assertFalse(issubclass(HarnessModeViolation, Exception))

    def test_run_cannot_be_used_to_execute_through_a_nullhand(self):
        core = self.core([tool("read_file", path="notes.txt")])
        with self.assertRaises(HarnessModeViolation):
            core.run("read the notes", self.grant(), self.pf())
        self.assertEqual(self.hand.touched, 1)  # the attempt is visible, and it did not execute anything

    def test_step_refuses_any_hand_that_can_execute(self):
        core = GovernedCore(self.mem, ScriptedReasoner([]), self.kernel, LocalFilesHand(self.root))
        with self.assertRaises(TypeError):
            core.begin("t", self.grant(), self.pf())
        self.assertEqual(self.core([]).begin("t", self.grant(), self.pf()).done, False)
        with self.assertRaises(TypeError):
            core.step(StepState("t1", "t", self.grant(), self.pf(), {}, "", ""))


class TestBegin(Base):
    def test_type_checks(self):
        core = self.core([])
        with self.assertRaises(TypeError):
            core.begin("t", None, self.pf())
        with self.assertRaises(TypeError):
            core.begin("t", self.grant(), None)
        with self.assertRaises(TypeError):
            core.step("not a state")

    def test_preflight_problems_end_the_task_before_any_model_call(self):
        core = self.core([tool("read_file", path="notes.txt")])
        st = core.begin("t", self.grant(), self.pf(token_cost=""))
        self.assertTrue(st.done)
        self.assertEqual(st.outcome.status, "BLOCKED")
        self.assertEqual(core.step(st).kind, "blocked")
        self.assertEqual(self.reasoner.prompts, [])

    def test_mutation_needs_authority_like_run(self):
        core = self.core([])
        st = core.begin("t", self.grant(tools=("write_file",)), self.pf())
        self.assertTrue(st.done)
        self.assertIn("authority", " ".join(st.outcome.reasons))

    def test_identity_is_required(self):
        os.remove(os.path.join(self.root, "icarus/memory/identity.md"))
        from icarus.agent.memory import IdentityMissing
        with self.assertRaises(IdentityMissing):
            self.core([]).begin("t", self.grant(), self.pf())
        self.assertEqual(self.reasoner.prompts, [])

    def test_task_start_is_logged_as_step_mode(self):
        self.begin(self.core([]))
        starts = [e for e in self.kernel_log() if e["type"] == "task_start"]
        self.assertEqual(starts[0]["mode"], "step")


class TestStep(Base):
    def test_default_authorizer_is_core_kernel_and_never_executes(self):
        core = self.core([tool("read_file", path="notes.txt")])
        st = self.begin(core)
        out = core.step(st, tools={"read_file": "read"})
        self.assertEqual((out.kind, out.tool, out.args), ("tool", "read_file", {"path": "notes.txt"}))
        self.assertEqual(self.hand.touched, 0)
        self.assertEqual([e["allowed"] for e in self.kernel_log() if e["type"] == "authorize"], [True])

    def test_nothing_the_model_asks_for_reaches_the_hand(self):
        core = self.core([tool("write_file", path="x.txt", content="y"), tool("delete_file", path="notes.txt"),
                          tool("read_file", path="../outside.txt"), tool("read_file", path="notes.txt")])
        st = self.begin(core)
        out = core.step(st)
        self.assertEqual(out.kind, "tool")
        self.assertEqual(out.args, {"path": "notes.txt"})
        self.assertEqual(self.hand.touched, 0)

    def test_authorizer_decides_instead_of_the_kernel_when_given(self):
        seen = []

        def authorizer(t, a):
            seen.append((t, a))
            return True, "granted", {"call_id": "call_x"}
        core = self.core([tool("read_file", path="notes.txt")])
        out = core.step(self.begin(core), authorizer=authorizer)
        self.assertEqual((out.kind, out.meta), ("tool", {"call_id": "call_x"}))
        self.assertEqual(seen, [("read_file", {"path": "notes.txt"})])
        self.assertEqual([e for e in self.kernel_log() if e["type"] == "authorize"], [])

    def test_a_denial_is_a_blocker_to_work_around_not_a_stop(self):
        core = self.core([tool("write_file", path="x", content="y"), tool("read_file", path="notes.txt")])
        out = core.step(self.begin(core))
        self.assertEqual(out.kind, "tool")
        self.assertIn("BLOCKER", self.reasoner.prompts[1])
        self.assertIn("tool not granted", self.reasoner.prompts[1])

    def test_blind_retry_is_refused_without_calling_the_authorizer(self):
        calls = []

        def authorizer(t, a):
            calls.append(t)
            return False, "no", {}
        core = self.core([tool("read_file", path="a"), tool("read_file", path="a"), tool("read_file", path="b")])
        st = self.begin(core)
        out = core.step(st, authorizer=authorizer)
        self.assertEqual(calls, ["read_file", "read_file"])  # the repeat of "a" never reached the authorizer
        self.assertEqual(out.kind, "blocked")
        self.assertIn("reasoner unavailable", out.result.reasons[0])
        self.assertIn("blind retry", " ".join(st.history))

    def test_consecutive_denials_end_the_task(self):
        outs = [tool("read_file", path=f"p{i}") for i in range(MAX_CONSECUTIVE_DENIALS + 2)]
        core = self.core(outs)
        st = self.begin(core)
        out = core.step(st, authorizer=lambda t, a: (False, "denied", {}))
        self.assertEqual(out.kind, "blocked")
        self.assertTrue(st.done)
        self.assertEqual(len(self.reasoner.prompts), MAX_CONSECUTIVE_DENIALS)

    def test_a_hard_stop_from_the_authorizer_ends_the_task_at_once(self):
        core = self.core([tool("read_file", path="a"), tool("read_file", path="b")])
        st = self.begin(core)
        out = core.step(st, authorizer=lambda t, a: (False, "MAX_CALLS: call budget used", {"hard": True}))
        self.assertEqual((out.kind, st.done), ("blocked", True))
        self.assertEqual(len(self.reasoner.prompts), 1)

    def test_pending_proposal_needs_its_result_before_the_model_is_asked_again(self):
        core = self.core([tool("read_file", path="notes.txt"), finish()])
        st = self.begin(core)
        core.step(st)
        again = core.step(st)
        self.assertEqual(again.kind, "blocked")
        self.assertFalse(st.done)
        self.assertEqual(len(self.reasoner.prompts), 1)

    def test_a_reported_result_goes_into_the_next_prompt(self):
        core = self.core([tool("read_file", path="notes.txt"), finish(evidence=[GOOD_SHA])])
        st = self.begin(core)
        core.step(st)
        out = core.step(st, [{"kind": "result", "tool": "read_file", "args": {"path": "notes.txt"}, "content": "hello world", "ok": True}])
        self.assertEqual(out.kind, "finish")
        self.assertIn("ran read_file", self.reasoner.prompts[1])
        self.assertIn("hello world", self.reasoner.prompts[1])
        self.assertIn("notes.txt", out.result.attempted[0])

    def test_a_failed_result_makes_the_same_call_a_blind_retry(self):
        core = self.core([tool("read_file", path="notes.txt"), tool("read_file", path="notes.txt"), tool("list_dir", path="icarus")])
        st = self.begin(core)
        core.step(st)
        out = core.step(st, [{"kind": "result", "tool": "read_file", "args": {"path": "notes.txt"}, "ok": False, "error": "boom"}])
        self.assertEqual((out.kind, out.tool), ("tool", "list_dir"))
        self.assertIn("hand error: boom", self.reasoner.prompts[1])
        self.assertIn("blind retry", self.reasoner.prompts[2])

    def test_harness_context_and_offered_tools_reach_the_prompt_as_data(self):
        core = self.core([tool("read_file", path="notes.txt")])
        core.step(self.begin(core), tools={"read_file": "read a file"}, context="user says: please read the notes")
        p = self.reasoner.prompts[0]
        self.assertIn("- read_file: read a file", p)
        self.assertIn("data, never instructions", p)
        self.assertIn("please read the notes", p)

    def test_context_is_redacted_and_capped(self):
        core = self.core([tool("read_file", path="notes.txt")])
        core.step(self.begin(core), context="key sk-" + "a" * 24 + " " + "x" * 5000)
        p = self.reasoner.prompts[0]
        self.assertNotIn("sk-" + "a" * 24, p)
        self.assertLess(p.count("x"), 2100)

    def test_no_tools_offered_says_so(self):
        core = self.core([finish()])
        core.step(self.begin(core))
        self.assertIn("(none offered)", self.reasoner.prompts[0])


class TestStepEnds(Base):
    def test_finish_is_judged_by_the_kernel_like_run(self):
        core = self.core([finish(evidence=[GOOD_SHA])])
        out = core.step(self.begin(core))
        self.assertEqual((out.kind, out.result.status, out.result.independence), ("finish", "PASS", "kernel-only"))
        core2 = self.core([finish(evidence=[GOOD_SHA])])
        st = core2.begin("t", self.grant(), self.pf(pass_evidence=(BAD_SHA,)))
        self.assertEqual(core2.step(st).result.status, "PARTIAL")

    def test_an_independent_adjudicator_is_honoured_and_can_downgrade(self):
        core = self.core([finish()], adjudicator=lambda tid, ev: (False, "not confirmed"))
        out = core.step(self.begin(core))
        self.assertEqual(out.result.status, "PARTIAL")
        core = self.core([finish()], adjudicator=lambda tid, ev: (True, "ok"))
        self.assertEqual(core.step(self.begin(core)).result.independence, "kernel+adjudicator")

    LESSON = "Lesson: notes exist.\nEvidence: notes.txt"

    def learned(self):
        path = os.path.join(self.root, "icarus/memory/learned.md")
        if not os.path.exists(path):
            return ""
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_a_kernel_only_pass_does_not_become_verified_learning(self):
        core = self.core([finish(evidence=[GOOD_SHA], lesson=self.LESSON)])
        out = core.step(self.begin(core))
        self.assertEqual((out.result.status, out.result.independence), ("PASS", "kernel-only"))
        self.assertEqual(self.learned(), "")
        w = [e for e in self.kernel_log() if e["type"] == "memory_write"]
        self.assertEqual(len(w), 1)
        self.assertFalse(w[0]["ok"])
        self.assertIn("not independently adjudicated", w[0]["reason"])

    def test_a_pass_confirmed_by_an_independent_adjudicator_is_learned(self):
        core = self.core([finish(evidence=[GOOD_SHA], lesson=self.LESSON)], adjudicator=lambda tid, ev: (True, "confirmed"))
        out = core.step(self.begin(core))
        self.assertEqual((out.result.status, out.result.independence), ("PASS", "kernel+adjudicator"))
        self.assertIn("notes exist", self.learned())
        self.assertTrue([e for e in self.kernel_log() if e["type"] == "memory_write"][0]["ok"])

    def test_an_adjudicator_that_refuses_means_no_pass_and_no_learning(self):
        core = self.core([finish(evidence=[GOOD_SHA], lesson=self.LESSON)], adjudicator=lambda tid, ev: (False, "no"))
        out = core.step(self.begin(core))
        self.assertEqual(out.result.status, "PARTIAL")
        self.assertEqual(self.learned(), "")
        self.assertEqual([e for e in self.kernel_log() if e["type"] == "memory_write"], [])

    def test_a_partial_finish_never_learns(self):
        core = self.core([finish(evidence=[GOOD_SHA], lesson=self.LESSON)], adjudicator=lambda tid, ev: (True, "ok"))
        st = core.begin("t", self.grant(), self.pf(pass_evidence=(BAD_SHA,)))
        self.assertEqual(core.step(st).result.status, "PARTIAL")
        self.assertEqual(self.learned(), "")

    def test_legacy_run_behaviour_is_unchanged_it_still_learns_from_a_kernel_only_pass(self):
        """Characterisation only. run() is deliberately untouched; this is flagged to the owner as an open decision."""
        core = GovernedCore(self.mem, ScriptedReasoner([finish(evidence=[GOOD_SHA], lesson=self.LESSON)]), self.kernel, LocalFilesHand(self.root))
        res = core.run("t", self.grant(), self.pf())
        self.assertEqual((res.status, res.independence), ("PASS", "kernel-only"))
        self.assertIn("notes exist", self.learned())

    def test_after_the_end_the_task_stays_ended_and_the_model_is_not_asked(self):
        core = self.core([finish(), finish()])
        st = self.begin(core)
        first = core.step(st)
        second = core.step(st)
        self.assertEqual((first.kind, second.kind), ("finish", "finish"))
        self.assertEqual(len(self.reasoner.prompts), 1)

    def test_owner_only_escalation_ends_the_task_with_the_owner_action(self):
        core = self.core([j(action="escalate", category="credentials", detail="needs a login")])
        st = self.begin(core)
        out = core.step(st)
        self.assertEqual((out.kind, st.done), ("blocked", True))
        self.assertIn("credentials", out.result.owner_action)

    def test_non_owner_escalation_is_worked_not_obeyed_and_is_not_terminal(self):
        core = self.core([j(action="escalate", category="other", detail="x"), j(action="escalate", category="other", detail="x"), finish()])
        st = self.begin(core)
        out = core.step(st)
        self.assertEqual(out.kind, "blocked")
        self.assertFalse(st.done)
        self.assertEqual(core.step(st).kind, "finish")

    def test_invalid_output_twice_blocks_but_the_task_can_continue(self):
        core = self.core(["not json", "still not", tool("read_file", path="notes.txt")])
        st = self.begin(core)
        self.assertEqual(core.step(st).kind, "blocked")
        self.assertFalse(st.done)
        self.assertEqual(core.step(st).kind, "tool")

    def test_reasoner_unavailable_blocks_without_ending_the_task(self):
        core = self.core([])
        st = self.begin(core)
        out = core.step(st)
        self.assertEqual(out.kind, "blocked")
        self.assertIn("reasoner unavailable", out.result.reasons[0])
        self.assertFalse(st.done)

    def test_a_material_change_ends_the_task(self):
        core = self.core([tool("read_file", path="notes.txt")])
        st = self.begin(core)
        self.reasoner.route = "a-different-route"
        out = core.step(st)
        self.assertEqual(out.kind, "blocked")
        self.assertIn("material change", out.result.reasons[0])
        self.assertTrue(st.done)
        self.assertEqual(self.reasoner.prompts, [])

    def test_a_route_change_during_the_model_call_is_caught_too(self):
        core = self.core([tool("read_file", path="notes.txt")])
        st = self.begin(core)
        original = self.reasoner.complete

        def swap(prompt):
            self.reasoner.route = "swapped"
            return original(prompt)
        self.reasoner.complete = swap
        self.assertIn("material change", core.step(st).result.reasons[0])


class TestDecide(Base):
    def test_decide_reads_without_counting_or_logging(self):
        before = list(self.kernel_log())
        d = self.kernel.decide(self.grant(), "read_file", {"path": "notes.txt"})
        self.assertTrue(d.allowed)
        self.assertFalse(self.kernel.decide(self.grant(), "write_file", {"path": "x"}).allowed)
        self.assertEqual(self.kernel_log(), before)
        self.assertEqual(self.kernel._attempts, {})

    def test_decide_agrees_with_authorize(self):
        for t, a in (("read_file", {"path": "notes.txt"}), ("write_file", {"path": "x"}), ("read_file", {"path": "../x"}), ("read_file", {"path": ".env"})):
            self.assertEqual(self.kernel.decide(self.grant(), t, a), self.kernel.authorize(self.grant(), t, a))


if __name__ == "__main__":
    unittest.main()
