import json
import os
import tempfile
import unittest

from icarus.agent.governed import GovernedCore, GovernedKernel, NullHand, Preflight
from icarus.agent.kernel import Grant
from icarus.agent.memory import Memory
from icarus.agent.pilot import hookcore as H
from icarus.agent.pilot import modelslot as MS
from icarus.agent.pilot import session as S
from icarus.agent.reasoners import ScriptedReasoner
from tests.agent import test_session as TS

CATALOG = {  # every model-visible name in DSH's tool catalog package map (4 Nov 2026)
    "ask_user_question", "run_code", "exit_plan_mode", "bash", "pwsh", "cordis_define", "cordis_inspect_list", "cordis_inspect_query",
    "cordis_inspect_self", "cordis_run", "cordis_stop", "cordis_undefine", "str_replace_editor", "edit", "read", "read_image", "write",
    "glob", "grep", "terminal_close", "terminal_list", "terminal_open", "terminal_read", "terminal_send", "terminal_signal",
    "create_goal", "get_goal", "update_goal", "schedule_create", "schedule_delete", "schedule_list", "lsp", "ralph", "skill",
    "session_event_read", "session_event_search", "session_event_trace", "session_search", "session_trace", "subagent",
    "subagent_fork", "interrupt_agent", "list_agents", "send_message", "report", "job_kill", "job_list", "job_output", "todo_write",
    "workflow", "web_fetch", "web_search",
}


class TestPathMapper(unittest.TestCase):
    def setUp(self):
        self.m = H.PathMapper("C:/Users/the1m/work")

    def ok(self, raw, want, mapper=None):
        self.assertEqual((mapper or self.m).map(raw), (True, want), raw)

    def no(self, raw, mapper=None):
        ok, why = (mapper or self.m).map(raw)
        self.assertFalse(ok, f"{raw!r} should be refused, got {why!r}")
        return why

    def test_absolute_paths_in_every_windows_spelling(self):
        for raw in ("C:/Users/the1m/work/a.txt", "C:\\Users\\the1m\\work\\a.txt", "c:\\users\\THE1M\\Work\\a.txt", "C:/Users/the1m/work//a.txt"):
            self.ok(raw, "a.txt")
        self.ok("C:/Users/the1m/work/src/deep/b.py", "src/deep/b.py")

    def test_relative_paths_resolve_against_the_cwd_then_the_root(self):
        self.ok("a.txt", "a.txt")
        self.ok("./src/a.txt", "src/a.txt")
        self.ok("src\\a.txt", "src/a.txt")
        self.ok("a/./b", "a/b")
        sub = H.PathMapper("C:/Users/the1m/work", cwd="C:/Users/the1m/work/src")
        self.ok("a.txt", "src/a.txt", sub)

    def test_posix_roots_keep_their_case(self):
        m = H.PathMapper("/srv/Work")
        self.ok("/srv/Work/A.txt", "A.txt", m)
        self.no("/srv/work/A.txt", m)

    def test_refusals(self):
        for raw in ("C:/Users/the1m/work/../x", "../x", "a/../../b", "x/../y", "C:/Users/the1m/other/a.txt", "D:/work/a.txt", "/etc/x",
                    "//server/share/a", "\\\\server\\share\\a", "C:foo", "C:", "a.txt:stream", "C:/Users/the1m/work/a.txt:hidden",
                    "~/a", "%TEMP%/a", "$HOME/a", "", "   ", "a\x00b", None, 5, ["a"], "a./b", "a /b", "CON", "x/NUL", "x/aux.txt", "com3.log"):
            self.no(raw)

    def test_the_workdir_root_itself_is_not_addressable(self):
        self.assertIn("root", self.no("C:/Users/the1m/work"))
        self.assertIn("root", self.no("C:/Users/the1m/work/"))
        self.no(".")

    def test_a_sibling_with_the_same_prefix_is_outside(self):
        self.no("C:/Users/the1m/workshop/a.txt")

    def test_a_unc_path_is_never_mistaken_for_a_local_path_that_looks_the_same(self):
        m = H.PathMapper("/server/share")
        self.ok("/server/share/a.txt", "a.txt", m)
        self.assertIn("UNC", self.no("//server/share/a.txt", m))
        self.assertIn("UNC", self.no("\\\\server\\share\\a.txt", m))

    def test_constructor_refuses_a_bad_root_or_cwd(self):
        for root, cwd in (("work", None), ("C:/work", "C:/other"), ("C:/work", "relative"), ("", None)):
            with self.assertRaises(ValueError):
                H.PathMapper(root, cwd=cwd)


class TestPolicy(unittest.TestCase):
    def test_the_table_covers_exactly_the_documented_tools(self):
        self.assertEqual(set(H.DSH_TOOLS), CATALOG)

    def test_unknown_tools_have_no_class(self):
        pol = H.HookPolicy()
        for name in ("shell", "run", "Read", "read ", "", "cordis_other", "mcp__x__y"):
            self.assertIsNone(pol.classify(name, {}), name)

    def test_the_editor_is_read_or_write_by_command(self):
        pol = H.HookPolicy()
        self.assertEqual(pol.classify("str_replace_editor", {"command": "view"}), "read")
        for cmd in ("create", "str_replace", "insert", "", None, "VIEW", 5):
            self.assertEqual(pol.classify("str_replace_editor", {"command": cmd}), "write", cmd)
        self.assertEqual(pol.classify("str_replace_editor", None), "write")

    def test_dangerous_classes_are_denied_by_default(self):
        allowed = H.DEFAULT_ALLOWED_CLASSES
        for cls in ("exec", "code", "agent", "runtime", "net", "context", "future", "history"):
            self.assertNotIn(cls, allowed)
        self.assertEqual(allowed, {"read", "write", "editor", "meta"})

    def test_every_class_in_the_table_is_described(self):
        self.assertLessEqual({c for c, _ in H.DSH_TOOLS.values()} - {"editor"}, set(H.CLASS_NOTES) | {"editor"})

    def test_the_committed_coverage_table_is_the_generated_one(self):
        path = os.path.join(os.path.dirname(H.__file__), "COVERAGE.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.assertIn(H.coverage_markdown(), text)

    def test_owner_only_detection(self):
        pol = H.HookPolicy()
        self.assertEqual(pol.owner_only("cordis_run", "runtime", {}, [])[0], "security")
        for p in ("C:/u/work/.env", "a/.ENV.local", "keys/server.pem", "~/.ssh/config", "x/.aws/credentials", "id_rsa", "C:\\u\\.kube\\config", "a.kdbx"):
            self.assertEqual(pol.owner_only("read", "read", {}, [p])[0], "credentials", p)
        self.assertEqual(pol.owner_only("write", "write", {"content": "key sk-" + "a" * 24}, [])[0], "credentials")
        self.assertIsNone(pol.owner_only("read", "read", {"file_path": "src/app.py"}, ["src/app.py"]))
        self.assertIsNone(pol.owner_only("read", "read", {"file_path": "environment.md"}, ["environment.md"]))


TOOLS = ("read", "write", "edit", "glob", "grep", "bash", "str_replace_editor", "web_fetch", "todo_write", "cordis_define", "lsp")


class HookBase(TS.Base):
    def setUp(self):
        super().setUp()
        self.work = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.work, "icarus/memory"))
        os.makedirs(os.path.join(self.work, "icarus/agent"))
        os.makedirs(os.path.join(self.work, "src"))
        with open(os.path.join(self.work, "icarus/memory/identity.md"), "w") as f:
            f.write("# Icarus Identity")
        with open(os.path.join(self.work, "notes.txt"), "w") as f:
            f.write("hello world")
        self.kernel = GovernedKernel(os.path.join(self.work, "decisions.jsonl"), self.work)
        self.kgrant = Grant("T-hook", frozenset(TOOLS), max_calls=1000)
        self.mapper = H.PathMapper(self.work)
        self.adapter = H.MappedKernelAdapter(self.kernel, self.kgrant, self.mapper)
        self.charter = self.make_charter(boundaries={"tools": list(TOOLS), "path_scopes": [self.work], "max_calls": 100,
                                                     "expires_at": "2026-12-01T00:00:00Z", "spend_eur": 0}, self_work=None)
        self.hook = H.HookCore()

    def p(self, rel):
        return os.path.join(self.work, rel)

    def rec(self, **over):
        grants = {"tools": list(TOOLS), "path_scopes": [self.work], "max_calls": 50, "expires_at": "2026-11-05T00:00:00Z", "spend_eur": 0}
        base = dict(task_id="T-hook", executor_id="dsh-agent", execution="harness", cwd=self.work, grants=grants)
        base.update(over)
        return self.record(**base)

    def start(self, rec=None, adapter=None, register=True, **kw):
        self.sess = self.open(rec or self.rec(), kernel_check=adapter or self.adapter, **kw)
        if register:
            self.hook.register(self.sess)
        return self.sess

    def propose(self, tool, args):
        r = self.sess.propose(tool, args, "dsh-agent")
        self.assertEqual(r["decision"], "allow", r)
        return r["call_id"]

    def ask(self, call_id, tool, args, **extra):
        req = {"session_id": self.sess.session_id, "call_id": call_id, "tool": tool, "args": args}
        req.update(extra)
        return self.hook.decide(req)

    def entries(self, kind):
        return [e for e in S.Ledger.read(self.sess.ledger.path) if e["kind"] == kind]


class TestAdapter(HookBase):
    def check(self, tool, args, phase="proposal", adapter=None):
        return (adapter or self.adapter)(tool, args, phase)

    def test_a_path_under_the_root_is_mapped_and_allowed_by_the_real_kernel(self):
        self.assertEqual(self.check("read", {"file_path": self.p("notes.txt")}), (True, "granted"))
        self.assertEqual(self.check("read", {"file_path": "notes.txt"}), (True, "granted"))
        self.assertEqual(self.check("write", {"file_path": self.p("src/a.py"), "content": "x"}), (True, "granted"))

    def test_paths_outside_the_root_are_refused_before_the_kernel_is_asked(self):
        before = dict(self.kernel._attempts)
        ok, why = self.check("read", {"file_path": "/somewhere/else.txt"})
        self.assertFalse(ok)
        self.assertTrue(why.startswith("PATH_NOT_MAPPABLE"), why)
        self.assertEqual(self.kernel._attempts, before)

    def test_unknown_tools_are_denied(self):
        ok, why = self.check("shell_exec", {"command": "ls"})
        self.assertFalse(ok)
        self.assertTrue(why.startswith("UNCLASSIFIED_TOOL"), why)

    def test_dangerous_classes_are_denied_but_the_policy_can_open_one_on_purpose(self):
        for tool, args in (("bash", {"command": "ls", "workdir": self.work}), ("web_fetch", {"url": "https://x.example"})):
            ok, why = self.check(tool, args)
            self.assertFalse(ok)
            self.assertTrue(why.startswith("CLASS_NOT_ALLOWED"), why)
        opened = H.MappedKernelAdapter(self.kernel, self.kgrant, self.mapper, H.HookPolicy(allowed_classes=H.DEFAULT_ALLOWED_CLASSES | {"exec"}))
        self.assertEqual(self.check("bash", {"command": "ls", "workdir": self.p("src")}, adapter=opened), (True, "granted"))
        self.assertFalse(self.check("bash", {"command": "ls", "workdir": self.work}, adapter=opened)[0])  # the root itself is not addressable

    def test_loading_code_into_the_runtime_is_an_owner_only_security_matter(self):
        ok, why = self.check("cordis_define", {"name": "x"})
        self.assertFalse(ok)
        self.assertTrue(why.startswith("OWNER_ONLY:security:"), why)

    def test_credential_paths_and_secret_arguments_are_owner_only(self):
        for tool, args in (("read", {"file_path": self.p(".env")}), ("read", {"file_path": self.p("keys/server.pem")}),
                           ("read", {"file_path": self.p(".ssh/id_rsa")}), ("write", {"file_path": self.p("a.txt"), "content": "k sk-" + "z" * 24})):
            ok, why = self.check(tool, args)
            self.assertFalse(ok)
            self.assertTrue(why.startswith("OWNER_ONLY:credentials:"), (tool, why))

    def test_write_class_tools_cannot_touch_protected_paths_whatever_they_are_called(self):
        for tool in ("write", "edit"):
            for rel in ("icarus/agent/kernel.py", "icarus/memory/identity.md", ".git/config", ".github/workflows/x.yml"):
                ok, why = self.check(tool, {"file_path": self.p(rel), "content": "x", "old_string": "a", "new_string": "b"})
                self.assertFalse(ok)
                self.assertTrue(why.startswith("PROTECTED_PATH"), (tool, rel, why))
        self.assertEqual(self.check("read", {"file_path": self.p("icarus/agent/kernel.py")}), (True, "granted"))

    def test_the_editor_is_a_write_unless_it_only_views(self):
        self.assertEqual(self.check("str_replace_editor", {"command": "view", "path": self.p("icarus/agent/kernel.py")}), (True, "granted"))
        ok, why = self.check("str_replace_editor", {"command": "create", "path": self.p("icarus/agent/kernel.py"), "file_text": "x"})
        self.assertFalse(ok)
        self.assertTrue(why.startswith("PROTECTED_PATH"), why)

    def test_read_class_tools_must_name_a_path(self):
        for tool, args in (("glob", {"pattern": "**/*"}), ("grep", {"pattern": "x"}), ("read", {}), ("write", {"content": "x"}), ("edit", {"old_string": "a", "new_string": "b"})):
            ok, why = self.check(tool, args)
            self.assertFalse(ok)
            self.assertTrue(why.startswith("PATH_REQUIRED"), (tool, why))
        self.assertEqual(self.check("grep", {"pattern": "x", "path": self.p("src")}), (True, "granted"))
        self.assertEqual(self.check("glob", {"pattern": "*.py", "path": "src"}), (True, "granted"))

    def test_every_path_value_is_checked_not_only_the_first(self):
        ok, why = self.check("edit", {"file_path": self.p("notes.txt"), "workdir": "/somewhere/else", "old_string": "a", "new_string": "b"})
        self.assertFalse(ok)
        self.assertIn("workdir", why)
        ok, why = self.check("read", {"file_path": [self.p("notes.txt"), "../../outside.txt"]})
        self.assertFalse(ok)
        ok, why = self.check("read", {"file_path": self.p("notes.txt"), "path": self.p("icarus/agent/kernel.py"), "dir": self.p("src")})
        self.assertTrue(ok, why)

    def test_the_kernel_judges_every_path_value_not_only_the_first(self):
        narrow = H.MappedKernelAdapter(self.kernel, Grant("T-narrow", frozenset({"read"}), allowed_paths=("src/",)), self.mapper)
        self.assertTrue(self.check("read", {"file_path": self.p("src/a.py")}, adapter=narrow)[0])
        ok, why = self.check("read", {"file_path": self.p("src/a.py"), "path": self.p("notes.txt")}, adapter=narrow)
        self.assertEqual((ok, why), (False, "path outside grant"))
        ok, why = self.check("read", {"file_path": [self.p("src/a.py"), self.p("src/b.py"), self.p("notes.txt")]}, adapter=narrow)
        self.assertEqual((ok, why), (False, "path outside grant"))

    def test_a_secret_marker_in_an_extra_path_value_is_still_caught(self):
        ok, why = self.check("read", {"file_path": self.p("notes.txt"), "dir": self.p(".aws")})
        self.assertFalse(ok)
        self.assertTrue(why.startswith("OWNER_ONLY:credentials"), why)

    def test_the_kernel_is_counted_once_at_proposal_and_only_re_read_at_execution(self):
        args = {"file_path": self.p("notes.txt")}
        self.check("read", args, "proposal")
        self.assertEqual(self.kernel._attempts["T-hook"], 1)
        self.check("read", args, "execution")
        self.assertEqual(self.kernel._attempts["T-hook"], 1)

    def test_a_tool_the_kernel_grant_lacks_is_denied_by_the_kernel(self):
        narrow = H.MappedKernelAdapter(self.kernel, Grant("T-hook", frozenset({"read"})), self.mapper)
        ok, why = self.check("write", {"file_path": self.p("a.txt"), "content": "x"}, adapter=narrow)
        self.assertEqual((ok, why), (False, "tool not granted"))

    def test_non_object_arguments_are_treated_as_empty(self):
        ok, why = self.check("read", "notes.txt")
        self.assertFalse(ok)
        self.assertTrue(why.startswith("PATH_REQUIRED"), why)

    def test_kernel_budget_exhaustion_is_a_denial(self):
        small = H.MappedKernelAdapter(self.kernel, Grant("T-small", frozenset({"read"}), max_calls=1), self.mapper)
        self.assertTrue(self.check("read", {"file_path": self.p("notes.txt")}, adapter=small)[0])
        self.assertEqual(self.check("read", {"file_path": self.p("notes.txt")}, adapter=small), (False, "budget exhausted"))


class TestHookDecision(HookBase):
    def setUp(self):
        super().setUp()
        self.start()
        self.args = {"file_path": self.p("notes.txt")}

    def test_register_only_accepts_mapped_harness_sessions(self):
        plain = self.open(self.rec(), kernel_check=TS.NamedKernel())
        with self.assertRaises(ValueError):
            self.hook.register(plain)
        core_mode = self.open(self.rec(execution="core"), kernel_check=self.adapter)
        with self.assertRaises(ValueError):
            self.hook.register(core_mode)

    def test_an_exact_call_is_allowed_in_the_contract_shape(self):
        cid = self.propose("read", self.args)
        r = self.ask(cid, "read", self.args, cwd=self.work, harness="dsh", harness_version="0.2.0-rc.2")
        self.assertEqual({k: r[k] for k in ("decision", "code", "escalation")}, {"decision": "allow", "code": "OK", "escalation": None})
        self.assertIsInstance(r["ledger_seq"], int)
        self.assertEqual(set(r), {"decision", "code", "reason", "ledger_seq", "escalation"})
        self.assertEqual(self.sess.calls[cid]["state"], "EXECUTED")

    def test_the_same_call_cannot_be_allowed_twice(self):
        cid = self.propose("read", self.args)
        self.ask(cid, "read", self.args)
        self.assertEqual(self.ask(cid, "read", self.args)["code"], "DUPLICATE_EXECUTION")

    def test_a_call_nobody_proposed_is_denied(self):
        self.assertEqual(self.ask("call_invented", "read", self.args)["code"], "UNPROPOSED_CALL")

    def test_changed_arguments_or_tool_are_denied_and_burn_the_call(self):
        cid = self.propose("read", self.args)
        r = self.ask(cid, "read", {"file_path": self.p("src/other.txt")})
        self.assertEqual((r["decision"], r["code"]), ("deny", "ARGS_MISMATCH"))
        self.assertEqual(self.ask(cid, "read", self.args)["code"], "CALL_BURNED")
        cid2 = self.propose("read", self.args)
        self.assertEqual(self.ask(cid2, "write", self.args)["code"], "TOOL_MISMATCH")

    def test_unknown_sessions_and_malformed_requests_are_denied_without_touching_anything(self):
        bad = [None, [], "x", {}, {"session_id": "s", "call_id": "c", "tool": "read"}, {"session_id": "s", "call_id": "c", "tool": "", "args": {}},
               {"session_id": 5, "call_id": "c", "tool": "read", "args": {}}, {"session_id": "s", "call_id": "c", "tool": "read", "args": []},
               {"session_id": "s", "call_id": "c", "tool": "read", "args": {}, "cwd": 5}]
        for req in bad:
            self.assertEqual(self.hook.decide(req)["code"], "BAD_REQUEST", req)
        self.assertEqual(self.hook.decide({"session_id": "nope", "call_id": "c", "tool": "read", "args": {}})["code"], "UNKNOWN_SESSION")
        self.assertEqual(self.entries("execution_authorized"), [])

    def test_unknown_extra_fields_are_ignored(self):
        cid = self.propose("read", self.args)
        self.assertEqual(self.ask(cid, "read", self.args, surprise="x")["decision"], "allow")

    def test_a_policy_tightened_after_the_proposal_denies_and_burns(self):
        opened = H.MappedKernelAdapter(self.kernel, self.kgrant, self.mapper, H.HookPolicy(allowed_classes=H.DEFAULT_ALLOWED_CLASSES | {"exec"}))
        self.start(adapter=opened)
        args = {"command": "ls", "workdir": self.p("src")}
        cid = self.propose("bash", args)
        opened.policy.allowed_classes = H.DEFAULT_ALLOWED_CLASSES
        r = self.ask(cid, "bash", args)
        self.assertEqual((r["decision"], r["code"]), ("deny", "KERNEL_DENIED"))
        self.assertIn("CLASS_NOT_ALLOWED", r["reason"])
        self.assertEqual(self.sess.calls[cid]["state"], "BURNED")
        self.assertEqual([e["code"] for e in self.entries("call_burned")], ["KERNEL_DENIED"])

    def test_an_owner_only_refusal_returns_an_escalation_and_burns_without_waiting(self):
        cid = self.propose("read", self.args)
        self.adapter.policy.secret_markers += ("notes",)
        r = self.ask(cid, "read", self.args)
        self.assertEqual((r["decision"], r["code"]), ("deny", "OWNER_ONLY"))
        esc = r["escalation"]
        self.assertEqual(set(esc), {"category", "owner_action", "evidence"})
        self.assertEqual(esc["category"], "credentials")
        self.assertTrue(esc["owner_action"].startswith("OWNER ASSISTANCE REQUIRED - "))
        self.assertEqual(self.sess.calls[cid]["state"], "BURNED")
        self.assertEqual(self.entries("owner_escalation")[0]["category"], "credentials")

    def test_owner_only_is_stopped_at_proposal_time_too(self):
        r = self.sess.propose("cordis_define", {"name": "x"}, "dsh-agent")
        self.assertEqual((r["decision"], r["code"]), ("deny", "KERNEL_DENIED"))
        self.assertTrue(r["reason"].startswith("OWNER_ONLY:security:"))
        self.assertEqual(self.sess.calls, {})

    def test_escalation_categories_are_only_the_owner_only_set(self):
        self.assertEqual(set(H.DECISION_ESCALATIONS), H.OWNER_ONLY)
        self.assertEqual(H.OWNER_ONLY, {"credentials", "security", "legal", "payment", "safety"})

    def test_a_paused_session_denies_without_burning(self):
        cid = self.propose("read", self.args)
        self.sess.state = "PAUSED_FOR_REVIEW"
        r = self.ask(cid, "read", self.args)
        self.assertEqual((r["decision"], r["code"]), ("deny", "PAUSED"))
        self.assertEqual(self.sess.calls[cid]["state"], "AUTHORIZED")

    def test_a_session_that_is_not_live_ready_is_denied(self):
        cid = self.propose("read", self.args)
        self.sess.verifier.available = False
        self.assertEqual(self.ask(cid, "read", self.args)["code"], "NOT_LIVE_READY")
        self.assertEqual(self.sess.calls[cid]["state"], "AUTHORIZED")

    def test_a_ledger_that_cannot_be_written_denies_and_executes_nothing(self):
        cid = self.propose("read", self.args)
        self.sess.ledger.path = self.work
        r = self.ask(cid, "read", self.args)
        self.assertEqual((r["decision"], r["code"]), ("deny", "LEDGER_UNAVAILABLE"))
        self.assertEqual(self.sess.calls[cid]["state"], "AUTHORIZED")

    def test_a_broken_kernel_denies_and_leaves_the_call_open(self):
        cid = self.propose("read", self.args)

        def boom(*a, **k):
            raise RuntimeError("kernel down")
        self.kernel.decide = boom
        r = self.ask(cid, "read", self.args)
        self.assertEqual((r["decision"], r["code"]), ("deny", "KERNEL_ERROR"))
        self.assertEqual(self.sess.calls[cid]["state"], "AUTHORIZED")

    def test_any_unexpected_error_is_a_denial_that_leaks_nothing(self):
        cid = self.propose("read", self.args)

        def boom(*a, **k):
            raise RuntimeError("secret internal detail")
        self.sess.authorize_execution = boom
        r = self.ask(cid, "read", self.args)
        self.assertEqual((r["decision"], r["code"]), ("deny", "INTERNAL"))
        self.assertNotIn("secret internal detail", json.dumps(r))

    def test_every_denial_path_returns_a_complete_reply_and_never_allows(self):
        cid = self.propose("read", self.args)
        replies = [self.hook.decide(None), self.hook.decide({}), self.ask("c", "read", {}), self.ask(cid, "read", {"file_path": "x"})]
        for r in replies:
            self.assertEqual(set(r), {"decision", "code", "reason", "ledger_seq", "escalation"})
            self.assertEqual(r["decision"], "deny")

    def test_the_hook_core_never_touches_the_filesystem(self):
        before = set(os.listdir(self.work))
        cid = self.propose("write", {"file_path": self.p("src/new.py"), "content": "x"})
        self.assertEqual(self.ask(cid, "write", {"file_path": self.p("src/new.py"), "content": "x"})["decision"], "allow")
        self.assertEqual(set(os.listdir(self.work)) - before, {"decisions.jsonl"})  # only the kernel's own decision log appears
        self.assertEqual(os.listdir(self.p("src")), [])
        self.assertFalse(os.path.exists(self.p("src/new.py")))


class TestThroughTheSlot(HookBase):
    """The mapped adapter in the real slot flow: proposals use absolute paths, the hook decides, results come back."""

    def test_an_absolute_path_proposal_goes_through_the_slot_and_the_hook(self):
        mem = Memory(self.work)
        reasoner = ScriptedReasoner([json.dumps({"action": "tool", "tool": "read", "args": {"file_path": self.p("notes.txt")}}),
                                     json.dumps({"action": "finish", "claim": "read it", "evidence": []})])
        core = GovernedCore(mem, reasoner, self.kernel, NullHand("harness:dsh"))
        runtime = MS.SlotRuntime(core)
        sess = self.start()
        pf = Preflight(endpoint="harness:dsh", token_cost="~2k", monetary_cost=0, owner="icarus", effort="low",
                       pass_evidence=({"kind": "file_exists", "path": "notes.txt"},), blockers=(), target="notes.txt@live-readback")
        token = runtime.register(sess, "read the notes", self.kgrant, pf)
        read_tool = {"type": "function", "function": {"name": "read", "description": "Read a file", "parameters": {"type": "object"}}}
        body = {"model": "icarus", "messages": [{"role": "user", "content": "read notes"}], "tools": [read_tool]}
        status, p = runtime.handle_chat(token, body)
        self.assertEqual(status, 200)
        tc = p["choices"][0]["message"]["tool_calls"][0]
        args = json.loads(tc["function"]["arguments"])
        self.assertEqual(args, {"file_path": self.p("notes.txt")})
        self.assertEqual(self.ask(tc["id"], "read", args)["decision"], "allow")
        msgs = body["messages"] + [{"role": "assistant", "content": None, "tool_calls": [tc]}, {"role": "tool", "tool_call_id": tc["id"], "content": "hello world"}]
        status, final = runtime.handle_chat(token, dict(body, messages=msgs))
        self.assertEqual(status, 200)
        self.assertTrue(final["choices"][0]["message"]["content"].startswith("RESULT: PARTIAL"))
        self.assertTrue(S.Ledger.verify(sess.ledger.path)[0])

    def test_a_dangerous_proposal_never_reaches_the_harness(self):
        mem = Memory(self.work)
        reasoner = ScriptedReasoner([json.dumps({"action": "tool", "tool": "bash", "args": {"command": "rm -rf x", "workdir": self.p("src")}}),
                                     json.dumps({"action": "tool", "tool": "read", "args": {"file_path": self.p(".env")}}),
                                     json.dumps({"action": "tool", "tool": "read", "args": {"file_path": self.p("notes.txt")}})])
        core = GovernedCore(mem, reasoner, self.kernel, NullHand("harness:dsh"))
        runtime = MS.SlotRuntime(core)
        sess = self.start()
        pf = Preflight(endpoint="harness:dsh", token_cost="~2k", monetary_cost=0, owner="icarus", effort="low",
                       pass_evidence=({"kind": "file_exists", "path": "notes.txt"},), blockers=(), target="notes.txt@live-readback")
        token = runtime.register(sess, "read the notes", self.kgrant, pf)
        tools = [{"type": "function", "function": {"name": n, "description": n, "parameters": {"type": "object"}}} for n in ("bash", "read")]
        status, p = runtime.handle_chat(token, {"model": "icarus", "messages": [{"role": "user", "content": "go"}], "tools": tools})
        self.assertEqual(status, 200)
        self.assertEqual(p["choices"][0]["message"]["tool_calls"][0]["function"]["name"], "read")
        denied = [e for e in S.Ledger.read(sess.ledger.path) if e["kind"] == "proposal_denied"]
        self.assertEqual([e["code"] for e in denied], ["KERNEL_DENIED", "KERNEL_DENIED"])
        self.assertEqual(len([e for e in S.Ledger.read(sess.ledger.path) if e["kind"] == "proposal"]), 1)


if __name__ == "__main__":
    unittest.main()
