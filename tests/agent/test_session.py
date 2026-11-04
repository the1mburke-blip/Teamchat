import ast
import base64
import copy
import inspect
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from icarus.agent.pilot import session as S

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    HAVE_CRYPTO = True
except Exception:  # pragma: no cover
    HAVE_CRYPTO = False


def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def write_text(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class Clock:
    def __init__(self):
        self.t = datetime(2026, 11, 4, 18, 0, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += timedelta(**kw)

    def iso(self, **kw):
        return (self.t + timedelta(**kw)).strftime("%Y-%m-%dT%H:%M:%SZ")


class StubVerifier:
    def __init__(self, available):
        self.available = available

    def verify(self, *a):
        if not self.available:
            raise S.AuthorityError("BLOCKED_NO_VERIFIER")
        return True


class Key:
    def __init__(self, ident, role):
        self.id, self.role = ident, role
        self.sk = Ed25519PrivateKey.generate()
        raw = self.sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.pub = base64.b64encode(raw).decode()

    def principal(self):
        return {"id": self.id, "role": self.role, "public_key": self.pub, "public_key_fingerprint": S.fingerprint(self.pub)}

    def sign(self, obj):
        body = {k: v for k, v in obj.items() if k != "signature"}
        return base64.b64encode(self.sk.sign(S.canonical(body))).decode()


# ---------------------------------------------------------------- no-crypto tests

class TestPrimitives(unittest.TestCase):
    def test_canonical_ignores_key_order_and_whitespace(self):
        self.assertEqual(S.canonical({"b": 1, "a": [1, 2]}), S.canonical(json.loads('{ "a":[1, 2],   "b":1 }')))

    def test_norm_path_refuses_traversal_and_junk(self):
        for bad in ("C:/work/../secret", "../x", "a/../../b", "", "a\x00b", None, 5):
            self.assertIsNone(S.norm_path(bad), bad)

    def test_norm_path_windows_forms_agree(self):
        self.assertEqual(S.norm_path("C:\\Work\\Docs\\"), S.norm_path("c:/work/docs"))

    def test_path_within_is_not_a_string_prefix_check(self):
        self.assertTrue(S.path_within("C:/work/docs/a.txt", "C:/work"))
        self.assertTrue(S.path_within("C:/work", "C:/work"))
        self.assertFalse(S.path_within("C:/workshop/a.txt", "C:/work"))
        self.assertFalse(S.path_within("C:/work/../etc", "C:/work"))

    def test_states_have_no_pass(self):
        self.assertNotIn("PASS", S.STATES)
        self.assertEqual(S.DEFAULT_SPEND_EUR, 0)

    def test_session_cannot_be_constructed_directly(self):
        with self.assertRaises(TypeError):
            S.Session()


class TestLedger(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.path = os.path.join(self.d, "l.jsonl")

    def test_chain_verifies(self):
        L = S.Ledger(self.path)
        for i in range(4):
            L.append("slot", "x", "s", "t", n=i)
        ok, msg = S.Ledger.verify(self.path)
        self.assertTrue(ok, msg)
        self.assertEqual([e["seq"] for e in S.Ledger.read(self.path)], [1, 2, 3, 4])

    def test_tampering_is_detected(self):
        L = S.Ledger(self.path)
        for i in range(3):
            L.append("slot", "x", "s", "t", n=i)
        lines = read_text(self.path).splitlines()
        e = json.loads(lines[1])
        e["n"] = 99
        lines[1] = json.dumps(e, sort_keys=True)
        write_text(self.path, "\n".join(lines) + "\n")
        self.assertFalse(S.Ledger.verify(self.path)[0])

    def test_deleted_entry_is_detected(self):
        L = S.Ledger(self.path)
        for i in range(3):
            L.append("slot", "x", "s", "t", n=i)
        lines = read_text(self.path).splitlines()
        write_text(self.path, "\n".join([lines[0], lines[2]]) + "\n")
        self.assertFalse(S.Ledger.verify(self.path)[0])

    def test_new_ledger_only(self):
        S.Ledger(self.path)
        with self.assertRaises(S.LedgerError) as cm:
            S.Ledger(self.path)
        self.assertEqual(cm.exception.code, "LEDGER_EXISTS")

    def test_unwritable_location_fails_closed(self):
        blocker = os.path.join(self.d, "file")
        open(blocker, "w").close()
        with self.assertRaises(S.LedgerError) as cm:
            S.Ledger(os.path.join(blocker, "sub", "l.jsonl"))
        self.assertEqual(cm.exception.code, "LEDGER_UNWRITABLE")


class TestNoVerifier(unittest.TestCase):
    def test_everything_signed_is_blocked_without_a_verifier(self):
        stub = StubVerifier(False)
        with self.assertRaises(S.AuthorityError) as cm:
            S.Charter.load({}, stub, "sha256:x")
        self.assertEqual(cm.exception.code, "BLOCKED_NO_VERIFIER")
        with self.assertRaises(S.AuthorityError) as cm:
            S.Session.open({}, "sig", None, "/tmp/never", stub)
        self.assertEqual(cm.exception.code, "BLOCKED_NO_VERIFIER")

    def test_none_verifier_is_blocked_too(self):
        with self.assertRaises(S.AuthorityError) as cm:
            S.Session.open({}, "sig", None, "/tmp/never", None)
        self.assertEqual(cm.exception.code, "BLOCKED_NO_VERIFIER")

    def test_real_verifier_reports_availability_honestly(self):
        self.assertEqual(S.Ed25519Verifier().available, HAVE_CRYPTO)


class TestPreservesM1(unittest.TestCase):
    def test_imports_nothing_from_m1_modules(self):
        tree = ast.parse(read_text(S.__file__))
        m1 = {"kernel", "core", "memory", "hands", "reasoners", "governed"}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = (node.module or "").split(".")
                self.assertEqual(node.level, 0, ast.dump(node))
                self.assertFalse("icarus" in mod and set(mod) & m1, ast.dump(node))
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.assertFalse(a.name.startswith("icarus"), a.name)

    def test_uses_standard_library_plus_optional_cryptography_only(self):
        tree = ast.parse(read_text(S.__file__))
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots |= {a.name.split(".")[0] for a in node.names}
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                roots.add(node.module.split(".")[0])
        self.assertLessEqual(roots, {"__future__", "base64", "hashlib", "json", "os", "re", "threading", "datetime", "cryptography"})


# ---------------------------------------------------------------- signed tests

class Base(unittest.TestCase):
    def setUp(self):
        if not HAVE_CRYPTO:
            self.skipTest("cryptography not installed; signing tests cannot run")
        self.clock = Clock()
        self.verifier = S.Ed25519Verifier()
        self.owner = Key("owner-michael", "owner")
        self.icarus = Key("icarus", "adjudicator")
        self.verifier_key = Key("verifier-1", "verifier")
        self.rogue = Key("rogue", "owner")
        self.tmp = tempfile.mkdtemp()
        self.n = 0
        self.charter = self.make_charter()

    # ---- builders
    def charter_record(self, **over):
        rec = {
            "charter_id": "c1", "owner_id": "owner-michael", "objectives": ["build the pilot"],
            "boundaries": {"tools": ["read_file", "write_file", "list_dir"], "path_scopes": ["C:/work"], "max_calls": 100,
                           "expires_at": "2026-12-01T00:00:00Z", "spend_eur": 0, "owner_only": ["credentials"]},
            "self_work": {"tools": ["read_file"], "path_scopes": ["C:/work/icarus-own"], "max_calls": 10,
                          "expires_at": "2026-11-30T00:00:00Z", "spend_eur": 0},
            "principals": [self.owner.principal(), self.icarus.principal(), self.verifier_key.principal()],
            "signer_id": "owner-michael",
        }
        rec.update(over)
        rec["signature"] = self.owner.sign(rec)
        return rec

    def make_charter(self, **over):
        return S.Charter.load(self.charter_record(**over), self.verifier, S.fingerprint(self.owner.pub), self.clock)

    def reviewers(self, *keys):
        return [k.principal() for k in keys]

    def milestones(self):
        return [
            {"id": "m1", "goal": "read the docs", "grants": {"tools": ["read_file"], "path_scopes": ["C:/work/docs"]},
             "evidence_required": ["commit_sha", "blob_verify"]},
            {"id": "m2", "goal": "write the module", "grants": {"tools": ["write_file"], "path_scopes": ["C:/work/src"]},
             "evidence_required": ["commit_sha", "test_run"]},
        ]

    def plan(self, approved_by="icarus", milestones=None):
        ms = milestones if milestones is not None else self.milestones()
        return {"plan_sha256": S.sha256_hex(S.canonical(ms)), "approved_by": approved_by, "milestones": ms}

    def record(self, plan=False, **over):
        self.n += 1
        rec = {
            "session_id": f"s{self.n}", "task_id": f"T{self.n}", "issued_by": "icarus", "signer_id": "icarus",
            "executor_id": "agent-1", "execution": "harness", "cwd": "C:/work/docs",
            "grants": {"tools": ["read_file", "write_file"], "path_scopes": ["C:/work/docs", "C:/work/src"], "max_calls": 5,
                       "expires_at": "2026-11-05T00:00:00Z", "spend_eur": 0},
            "reviewers": self.reviewers(self.owner, self.icarus, self.verifier_key),
        }
        if plan:
            rec["checkpoint_plan"] = self.plan()
        rec.update(over)
        return rec

    def open(self, rec=None, signer=None, charter=None, plan=False, kernel_check=None, verifier=None):
        rec = rec or self.record(plan=plan)
        signer = signer or self.icarus
        sig = signer.sign(rec)
        path = os.path.join(self.tmp, rec["session_id"] + ".ledger.jsonl")
        return S.Session.open(rec, sig, charter or self.charter, path, verifier or self.verifier, self.clock, kernel_check)

    def code(self, fn, *a, **kw):
        with self.assertRaises(S.AuthorityError) as cm:
            fn(*a, **kw)
        return cm.exception.code

    def decision(self, sess, key, decision="resume", nonce="n1", **over):
        d = {"session_id": sess.session_id, "gate_id": sess.gate["gate_id"], "milestone_id": sess.gate["milestone_id"],
             "ledger_head_hash": sess.gate["ledger_head_hash"], "decision": decision, "nonce": nonce,
             "expires_at": self.clock.iso(hours=1), "reviewer_id": key.id}
        d.update(over)
        d["signature"] = key.sign(d)
        return d

    def reach(self, sess, milestone="m1"):
        ev = {"m1": [{"kind": "commit_sha", "ref": "abc1234"}, {"kind": "blob_verify", "ref": "def5678"}],
              "m2": [{"kind": "commit_sha", "ref": "abc1234"}, {"kind": "test_run", "ref": "76 passed"}]}[milestone]
        return sess.declare_milestone(milestone, ev)


class TestCharter(Base):
    def test_valid_charter_loads(self):
        self.assertEqual(self.charter.objectives, ["build the pilot"])
        self.assertEqual(self.charter.spend_ceiling(), 0)

    def test_wrong_pinned_owner_key_is_untrusted(self):
        self.assertEqual(self.code(S.Charter.load, self.charter_record(), self.verifier, S.fingerprint(self.rogue.pub), self.clock), "UNTRUSTED_CHARTER")

    def test_forged_charter_signed_by_another_key(self):
        rec = self.charter_record()
        rec["signature"] = self.rogue.sign(rec)
        self.assertEqual(self.code(S.Charter.load, rec, self.verifier, S.fingerprint(self.owner.pub), self.clock), "BAD_SIGNATURE")

    def test_tampered_boundaries_break_the_signature(self):
        rec = self.charter_record()
        rec["boundaries"]["max_calls"] = 10 ** 6
        self.assertEqual(self.code(S.Charter.load, rec, self.verifier, S.fingerprint(self.owner.pub), self.clock), "BAD_SIGNATURE")

    def test_charter_must_be_signed_by_an_owner_principal(self):
        rec = self.charter_record(signer_id="icarus")
        self.assertEqual(self.code(S.Charter.load, rec, self.verifier, S.fingerprint(self.icarus.pub), self.clock), "BAD_CHARTER")

    def test_principal_fingerprint_must_match_key(self):
        rec = self.charter_record()
        rec["principals"][1] = dict(rec["principals"][1], public_key=self.rogue.pub)
        rec["signature"] = self.owner.sign(rec)
        self.assertEqual(self.code(S.Charter.load, rec, self.verifier, S.fingerprint(self.owner.pub), self.clock), "BAD_CHARTER")

    def test_expired_charter(self):
        self.clock.advance(days=40)
        self.assertEqual(self.code(S.Charter.load, self.charter_record(), self.verifier, S.fingerprint(self.owner.pub), self.clock), "CHARTER_EXPIRED")

    def test_self_work_cannot_exceed_boundaries(self):
        rec = self.charter_record()
        rec["self_work"]["tools"] = ["read_file", "delete_everything"]
        rec["signature"] = self.owner.sign(rec)
        self.assertEqual(self.code(S.Charter.load, rec, self.verifier, S.fingerprint(self.owner.pub), self.clock), "ATTENUATION_VIOLATION")

    def test_spend_defaults_to_zero_when_unset(self):
        rec = self.charter_record()
        del rec["boundaries"]["spend_eur"]
        rec["signature"] = self.owner.sign(rec)
        c = S.Charter.load(rec, self.verifier, S.fingerprint(self.owner.pub), self.clock)
        self.assertEqual(c.spend_ceiling(), 0)


class TestIssuance(Base):
    def test_icarus_delegates_without_owner_approval(self):
        s = self.open()
        self.assertEqual(s.state, "ACTIVE")
        kinds = [e["kind"] for e in S.Ledger.read(s.ledger.path)]
        self.assertEqual(kinds[:2], ["session_opened", "no_plan"])

    def test_owner_can_issue_too(self):
        rec = self.record(issued_by="owner", signer_id="owner-michael")
        self.assertEqual(self.open(rec, signer=self.owner).state, "ACTIVE")

    def test_executor_cannot_grant_itself(self):
        rec = self.record(executor_id="icarus")
        self.assertEqual(self.code(self.open, rec), "SELF_GRANT")

    def test_unknown_signer(self):
        rec = self.record(signer_id="rogue")
        self.assertEqual(self.code(self.open, rec, signer=self.rogue), "UNKNOWN_SIGNER")

    def test_verifier_role_cannot_issue(self):
        rec = self.record(signer_id="verifier-1")
        self.assertEqual(self.code(self.open, rec, signer=self.verifier_key), "ROLE_NOT_ALLOWED")

    def test_signature_from_the_wrong_key(self):
        self.assertEqual(self.code(self.open, self.record(), signer=self.rogue), "BAD_SIGNATURE")

    def test_record_tampered_after_signing(self):
        rec = self.record()
        sig = self.icarus.sign(rec)
        rec["grants"]["max_calls"] = 99
        self.assertEqual(self.code(S.Session.open, rec, sig, self.charter, os.path.join(self.tmp, "x.jsonl"), self.verifier, self.clock), "BAD_SIGNATURE")

    def test_issued_by_must_match_the_signer_role(self):
        self.assertEqual(self.code(self.open, self.record(issued_by="owner")), "ISSUER_MISMATCH")
        rec = self.record(issued_by="icarus", signer_id="owner-michael")
        self.assertEqual(self.code(self.open, rec, signer=self.owner), "ISSUER_MISMATCH")

    def test_attenuation_tools(self):
        rec = self.record()
        rec["grants"]["tools"] = ["read_file", "shell"]
        self.assertEqual(self.code(self.open, rec), "ATTENUATION_VIOLATION")

    def test_attenuation_paths(self):
        rec = self.record()
        rec["grants"]["path_scopes"] = ["C:/workshop"]
        self.assertEqual(self.code(self.open, rec), "ATTENUATION_VIOLATION")
        rec = self.record()
        rec["grants"]["path_scopes"] = ["D:/"]
        self.assertEqual(self.code(self.open, rec), "ATTENUATION_VIOLATION")

    def test_attenuation_calls_expiry(self):
        rec = self.record()
        rec["grants"]["max_calls"] = 101
        self.assertEqual(self.code(self.open, rec), "ATTENUATION_VIOLATION")
        rec = self.record()
        rec["grants"]["expires_at"] = "2027-01-01T00:00:00Z"
        self.assertEqual(self.code(self.open, rec), "ATTENUATION_VIOLATION")

    def test_euro_zero_limit_cannot_be_raised_by_icarus_or_owner_sessions(self):
        rec = self.record()
        rec["grants"]["spend_eur"] = 0.01
        self.assertEqual(self.code(self.open, rec), "ATTENUATION_VIOLATION")
        rec = self.record(issued_by="owner", signer_id="owner-michael")
        rec["grants"]["spend_eur"] = 5
        self.assertEqual(self.code(self.open, rec, signer=self.owner), "ATTENUATION_VIOLATION")

    def test_spend_allowed_only_when_the_charter_allows_it(self):
        ch = self.make_charter(boundaries={"tools": ["read_file"], "path_scopes": ["C:/work"], "max_calls": 10,
                                           "expires_at": "2026-12-01T00:00:00Z", "spend_eur": 2},
                               self_work=None)
        rec = self.record()
        rec["grants"] = {"tools": ["read_file"], "path_scopes": ["C:/work/docs"], "max_calls": 3, "expires_at": "2026-11-05T00:00:00Z", "spend_eur": 1.5}
        s = self.open(rec, charter=ch)
        self.assertEqual(s.grants["spend_eur"], 1.5)

    def test_session_grants_need_an_expiry(self):
        rec = self.record()
        del rec["grants"]["expires_at"]
        self.assertEqual(self.code(self.open, rec), "BAD_GRANTS")

    def test_already_expired_session(self):
        rec = self.record()
        rec["grants"]["expires_at"] = "2026-11-04T17:00:00Z"
        self.assertEqual(self.code(self.open, rec), "SESSION_EXPIRED")

    def test_registry_cannot_contain_a_forged_reviewer(self):
        rec = self.record()
        rec["reviewers"].append({"id": "agent-1", "role": "owner", "public_key": self.rogue.pub, "public_key_fingerprint": S.fingerprint(self.rogue.pub)})
        self.assertEqual(self.code(self.open, rec), "REGISTRY_FORGED")

    def test_registry_cannot_swap_a_key_under_a_real_id(self):
        rec = self.record()
        rec["reviewers"][0] = dict(rec["reviewers"][0], public_key=self.rogue.pub)
        self.assertEqual(self.code(self.open, rec), "REGISTRY_FORGED")

    def test_registry_cannot_promote_a_role(self):
        rec = self.record()
        rec["reviewers"][2] = dict(rec["reviewers"][2], role="owner")
        self.assertEqual(self.code(self.open, rec), "REGISTRY_FORGED")

    def test_bad_execution_mode(self):
        self.assertEqual(self.code(self.open, self.record(execution="both")), "BAD_SESSION")

    def test_ledger_unwritable_fails_session_open(self):
        rec = self.record()
        blocker = os.path.join(self.tmp, "afile")
        open(blocker, "w").close()
        with self.assertRaises(S.LedgerError):
            S.Session.open(rec, self.icarus.sign(rec), self.charter, os.path.join(blocker, "x", "l.jsonl"), self.verifier, self.clock)


class TestSelfWork(Base):
    def self_rec(self, **over):
        rec = self.record(issued_by="charter", signer_id="icarus", executor_id="icarus")
        rec["grants"] = {"tools": ["read_file"], "path_scopes": ["C:/work/icarus-own"], "max_calls": 5,
                         "expires_at": "2026-11-05T00:00:00Z", "spend_eur": 0}
        rec.update(over)
        return rec

    def test_icarus_can_work_inside_the_charter_self_work_ceiling(self):
        s = self.open(self.self_rec())
        self.assertTrue(s.independent_required)
        self.assertEqual(s.issued_by, "charter")

    def test_self_work_cannot_exceed_the_ceiling(self):
        rec = self.self_rec()
        rec["grants"]["tools"] = ["read_file", "write_file"]
        self.assertEqual(self.code(self.open, rec), "ATTENUATION_VIOLATION")
        rec = self.self_rec()
        rec["grants"]["path_scopes"] = ["C:/work/docs"]
        self.assertEqual(self.code(self.open, rec), "ATTENUATION_VIOLATION")

    def test_no_self_work_without_charter_authority(self):
        ch = self.make_charter(self_work=None)
        self.assertEqual(self.code(self.open, self.self_rec(), charter=ch), "NO_SELF_WORK_AUTHORITY")

    def test_self_work_is_for_the_adjudicator_only(self):
        rec = self.self_rec(signer_id="owner-michael", executor_id="owner-michael")
        self.assertEqual(self.code(self.open, rec, signer=self.owner), "ISSUER_MISMATCH")

    def test_charter_self_work_must_be_executed_by_its_signer(self):
        self.assertEqual(self.code(self.open, self.self_rec(executor_id="agent-1")), "ISSUER_MISMATCH")

    def test_owner_assigning_work_to_icarus_also_needs_independent_review(self):
        rec = self.record(issued_by="owner", signer_id="owner-michael", executor_id="icarus")
        s = self.open(rec, signer=self.owner)
        self.assertTrue(s.independent_required)


class TestPlans(Base):
    def test_plan_loaded_and_gates_enabled(self):
        s = self.open(plan=True)
        kinds = [e["kind"] for e in S.Ledger.read(s.ledger.path)]
        self.assertIn("plan_loaded", kinds)
        self.assertNotIn("no_plan", kinds)
        self.assertEqual(s.active_milestone()["id"], "m1")

    def test_tampered_milestones_do_not_match_the_pinned_hash(self):
        rec = self.record(plan=True)
        rec["checkpoint_plan"]["milestones"][0]["evidence_required"] = ["commit_sha"]
        self.assertEqual(self.code(self.open, rec), "PLAN_INVALID")

    def test_milestone_without_evidence_requirement_is_refused(self):
        ms = self.milestones()
        ms[0]["evidence_required"] = []
        rec = self.record(checkpoint_plan=self.plan(milestones=ms))
        self.assertEqual(self.code(self.open, rec), "PLAN_INVALID")

    def test_empty_plan_is_refused_not_ignored(self):
        rec = self.record(checkpoint_plan=self.plan(milestones=[]))
        self.assertEqual(self.code(self.open, rec), "PLAN_INVALID")

    def test_duplicate_milestone_ids_refused(self):
        ms = self.milestones()
        ms[1]["id"] = "m1"
        self.assertEqual(self.code(self.open, self.record(checkpoint_plan=self.plan(milestones=ms))), "PLAN_INVALID")

    def test_milestone_grants_must_fit_inside_session_grants(self):
        ms = self.milestones()
        ms[1]["grants"]["tools"] = ["write_file", "list_dir"]
        self.assertEqual(self.code(self.open, self.record(checkpoint_plan=self.plan(milestones=ms))), "ATTENUATION_VIOLATION")

    def test_plan_must_be_approved_by_the_session_signer(self):
        rec = self.record(checkpoint_plan=self.plan(approved_by="owner-michael"))
        self.assertEqual(self.code(self.open, rec), "PLAN_INVALID")

    def test_a_plan_with_no_eligible_reviewer_is_refused_up_front(self):
        rec = self.record(plan=True, reviewers=[])
        self.assertEqual(self.code(self.open, rec), "NO_ELIGIBLE_REVIEWER")
        rec = self.record(plan=True, reviewers=self.reviewers(self.icarus), executor_id="agent-1")
        self.assertEqual(self.open(rec).state, "ACTIVE")  # icarus can review delegated work
        rec = self.record(plan=True, reviewers=self.reviewers(self.verifier_key), executor_id="verifier-1")
        self.assertEqual(self.code(self.open, rec), "NO_ELIGIBLE_REVIEWER")

    def test_icarus_own_work_needs_a_non_adjudicator_reviewer(self):
        rec = self.record(issued_by="owner", signer_id="owner-michael", executor_id="icarus", checkpoint_plan=self.plan(approved_by="owner-michael"),
                          reviewers=self.reviewers(self.icarus))
        self.assertEqual(self.code(self.open, rec, signer=self.owner), "NO_ELIGIBLE_REVIEWER")


class TestCalls(Base):
    def setUp(self):
        super().setUp()
        self.s = self.open()

    def prop(self, tool="read_file", args=None, **kw):
        return self.s.propose(tool, args if args is not None else {"path": "C:/work/docs/a.txt"}, "agent-1", **kw)

    def test_propose_allows_and_records_the_exact_arguments(self):
        r = self.prop()
        self.assertEqual(r["decision"], "allow")
        e = [x for x in S.Ledger.read(self.s.ledger.path) if x["kind"] == "proposal"][0]
        self.assertEqual(e["args_sha256"], S.sha256_hex(S.canonical({"path": "C:/work/docs/a.txt"})))
        self.assertTrue(e["args_saved"])
        saved = read_bytes(self.s.ledger.path + ".calls/" + r["call_id"] + ".json")
        self.assertEqual(saved, S.canonical({"path": "C:/work/docs/a.txt"}))

    def test_tool_not_in_grant(self):
        self.assertEqual(self.prop("shell", {"command": "ls"})["code"], "TOOL_NOT_GRANTED")

    def test_paths_outside_scope_or_traversing(self):
        self.assertEqual(self.prop(args={"path": "C:/secrets/a"})["code"], "PATH_OUT_OF_SCOPE")
        self.assertEqual(self.prop(args={"path": "C:/work/docs/../../secrets"})["code"], "PATH_OUT_OF_SCOPE")
        self.assertEqual(self.prop(args={"path": "C:/work/docs-evil/a"})["code"], "PATH_OUT_OF_SCOPE")
        self.assertEqual(self.prop(args={"path": ["C:/work/docs/a", "C:/elsewhere/b"]})["code"], "PATH_OUT_OF_SCOPE")
        self.assertEqual(self.prop(args={"path": 5})["code"], "PATH_OUT_OF_SCOPE")

    def test_relative_paths_resolve_against_the_session_cwd_only(self):
        self.assertEqual(self.prop(args={"path": "notes/a.txt"})["decision"], "allow")
        self.assertEqual(self.prop(args={"path": "../src/a.txt"})["code"], "PATH_OUT_OF_SCOPE")
        rec = self.record()
        del rec["cwd"]
        s2 = self.open(rec)
        self.assertEqual(s2.propose("read_file", {"path": "a.txt"}, "agent-1")["code"], "RELATIVE_PATH")

    def test_no_path_scopes_means_no_filesystem_access(self):
        rec = self.record()
        rec["grants"]["path_scopes"] = []
        s2 = self.open(rec)
        self.assertEqual(s2.propose("read_file", {"path": "C:/work/docs/a"}, "agent-1")["code"], "PATH_OUT_OF_SCOPE")

    def test_arguments_must_be_an_object(self):
        self.assertEqual(self.s.propose("read_file", ["C:/work/docs/a"], "agent-1")["code"], "BAD_ARGS")

    def test_call_budget(self):
        for _ in range(5):
            self.assertEqual(self.prop()["decision"], "allow")
        self.assertEqual(self.prop()["code"], "MAX_CALLS")

    def test_euro_zero_spend_default(self):
        self.assertEqual(self.prop(cost_eur=0)["decision"], "allow")
        self.assertEqual(self.prop(cost_eur=0.01)["code"], "SPEND_EXCEEDED")
        self.assertEqual(self.prop(cost_eur=-1)["code"], "BAD_COST")
        self.assertEqual(self.prop(cost_eur=True)["code"], "BAD_COST")
        self.assertEqual(self.s.spent_eur, 0)

    def test_kernel_check_applies_at_proposal_and_at_execution(self):
        flag = {"ok": True}
        s = self.open(kernel_check=lambda t, a: (flag["ok"], "kernel says no"))
        r = s.propose("read_file", {"path": "C:/work/docs/a"}, "agent-1")
        self.assertEqual(r["decision"], "allow")
        flag["ok"] = False
        self.assertEqual(s.authorize_execution(r["call_id"], "read_file", {"path": "C:/work/docs/a"}, "harness")["code"], "KERNEL_DENIED")
        self.assertEqual(s.propose("read_file", {"path": "C:/work/docs/a"}, "agent-1")["code"], "KERNEL_DENIED")

    def test_exact_match_executes_once(self):
        r = self.prop()
        a = {"path": "C:/work/docs/a.txt"}
        ok = self.s.authorize_execution(r["call_id"], "read_file", a, "harness")
        self.assertEqual(ok["decision"], "allow")
        self.assertEqual(self.s.authorize_execution(r["call_id"], "read_file", a, "harness")["code"], "DUPLICATE_EXECUTION")
        self.assertEqual(self.s.calls[r["call_id"]]["state"], "EXECUTED")

    def test_argument_key_order_does_not_matter(self):
        r = self.s.propose("write_file", {"path": "C:/work/src/a.txt", "content": "x"}, "agent-1")
        self.assertEqual(r["decision"], "allow")
        self.assertEqual(self.s.authorize_execution(r["call_id"], "write_file", {"content": "x", "path": "C:/work/src/a.txt"}, "harness")["decision"], "allow")

    def test_unproposed_call_is_denied(self):
        self.assertEqual(self.s.authorize_execution("call_made_up", "read_file", {"path": "C:/work/docs/a"}, "harness")["code"], "UNPROPOSED_CALL")

    def test_tool_mismatch_burns_the_call(self):
        r = self.prop()
        a = {"path": "C:/work/docs/a.txt"}
        self.assertEqual(self.s.authorize_execution(r["call_id"], "write_file", a, "harness")["code"], "TOOL_MISMATCH")
        self.assertEqual(self.s.authorize_execution(r["call_id"], "read_file", a, "harness")["code"], "CALL_BURNED")

    def test_args_mismatch_burns_the_call_even_for_one_character(self):
        r = self.prop()
        self.assertEqual(self.s.authorize_execution(r["call_id"], "read_file", {"path": "C:/work/docs/b.txt"}, "harness")["code"], "ARGS_MISMATCH")
        self.assertEqual(self.s.authorize_execution(r["call_id"], "read_file", {"path": "C:/work/docs/a.txt"}, "harness")["code"], "CALL_BURNED")

    def test_extra_or_injected_arguments_are_a_mismatch(self):
        r = self.prop()
        a = {"path": "C:/work/docs/a.txt", "args_sha256": "0" * 64}
        self.assertEqual(self.s.authorize_execution(r["call_id"], "read_file", a, "harness")["code"], "ARGS_MISMATCH")

    def test_no_hash_parameter_exists_for_the_harness_to_supply(self):
        params = inspect.signature(S.Session.authorize_execution).parameters
        self.assertFalse(any("sha" in p or "hash" in p for p in params))

    def test_non_object_arguments_at_execution(self):
        r = self.prop()
        self.assertEqual(self.s.authorize_execution(r["call_id"], "read_file", "C:/work/docs/a.txt", "harness")["code"], "ARGS_MISMATCH")

    def test_one_executor_per_session_mode(self):
        r = self.prop()
        self.assertEqual(self.s.authorize_execution(r["call_id"], "read_file", {"path": "C:/work/docs/a.txt"}, "core")["code"], "WRONG_EXECUTOR")
        core = self.open(self.record(execution="core"))
        r2 = core.propose("read_file", {"path": "C:/work/docs/a"}, "agent-1")
        self.assertEqual(core.authorize_execution(r2["call_id"], "read_file", {"path": "C:/work/docs/a"}, "harness")["code"], "WRONG_EXECUTOR")
        self.assertEqual(core.authorize_execution(r2["call_id"], "read_file", {"path": "C:/work/docs/a"}, "core")["decision"], "allow")

    def test_results_follow_execution_and_are_tagged_not_independent(self):
        r = self.prop()
        self.assertEqual(self.s.record_result(r["call_id"], "ok")["code"], "RESULT_NOT_EXPECTED")
        self.s.authorize_execution(r["call_id"], "read_file", {"path": "C:/work/docs/a.txt"}, "harness")
        self.assertEqual(self.s.record_result(r["call_id"], "ok")["decision"], "allow")
        self.assertEqual(self.s.record_result(r["call_id"], "again")["code"], "RESULT_NOT_EXPECTED")
        e = [x for x in S.Ledger.read(self.s.ledger.path) if x["kind"] == "tool_result"][0]
        self.assertEqual(e["source"], "harness_reported")
        self.assertEqual(e["args_sha256"], self.s.calls[r["call_id"]]["args_sha256"])

    def test_core_mode_results_are_tagged_core(self):
        core = self.open(self.record(execution="core"))
        r = core.propose("read_file", {"path": "C:/work/docs/a"}, "agent-1")
        core.authorize_execution(r["call_id"], "read_file", {"path": "C:/work/docs/a"}, "core")
        core.record_result(r["call_id"], b"bytes")
        e = [x for x in S.Ledger.read(core.ledger.path) if x["kind"] == "tool_result"][0]
        self.assertEqual(e["source"], "core_reported")

    def test_unmatched_result_is_logged_and_not_trusted(self):
        r = self.s.record_result("call_nope", "x")
        self.assertEqual(r["code"], "UNMATCHED_RESULT")
        self.assertIn("unmatched_tool_result", [e["kind"] for e in S.Ledger.read(self.s.ledger.path)])

    def test_expired_session_denies_everything(self):
        r = self.prop()
        self.clock.advance(days=2)
        self.assertEqual(self.prop()["code"], "SESSION_EXPIRED")
        self.assertEqual(self.s.authorize_execution(r["call_id"], "read_file", {"path": "C:/work/docs/a.txt"}, "harness")["code"], "SESSION_EXPIRED")

    def test_ledger_failure_fails_closed_and_leaves_no_call_behind(self):
        from unittest import mock
        before = (self.s.calls_authorized, len(self.s.calls))
        with mock.patch("icarus.agent.pilot.session.os.fsync", side_effect=OSError("disk gone")):
            with self.assertRaises(S.LedgerError):
                self.prop()
        self.assertEqual((self.s.calls_authorized, len(self.s.calls)), before)

    def test_ledger_chain_survives_a_mixed_run_and_never_says_pass(self):
        r = self.prop()
        self.s.authorize_execution(r["call_id"], "read_file", {"path": "C:/work/docs/a.txt"}, "harness")
        self.s.record_result(r["call_id"], "ok")
        self.prop(args={"path": "C:/other/outside.txt"})
        ok, msg = S.Ledger.verify(self.s.ledger.path)
        self.assertTrue(ok, msg)
        self.assertNotIn('"PASS"', read_text(self.s.ledger.path))

    def test_denials_are_logged_with_a_code(self):
        self.prop(args={"path": "C:/other/outside.txt"})
        e = S.Ledger.read(self.s.ledger.path)[-1]
        self.assertEqual((e["kind"], e["decision"], e["code"]), ("proposal_denied", "deny", "PATH_OUT_OF_SCOPE"))


class TestMilestones(Base):
    def setUp(self):
        super().setUp()
        self.s = self.open(plan=True)

    def test_only_the_active_milestone_grants_apply(self):
        self.assertEqual(self.s.propose("read_file", {"path": "C:/work/docs/a"}, "agent-1")["decision"], "allow")
        self.assertEqual(self.s.propose("write_file", {"path": "C:/work/src/a", "content": "x"}, "agent-1")["code"], "OUT_OF_MILESTONE")
        self.assertEqual(self.s.propose("read_file", {"path": "C:/work/src/a"}, "agent-1")["code"], "PATH_OUT_OF_SCOPE")

    def test_incomplete_evidence_does_not_open_a_gate(self):
        r = self.s.declare_milestone("m1", [{"kind": "commit_sha", "ref": "abc"}])
        self.assertEqual(r["code"], "MILESTONE_INCOMPLETE")
        self.assertEqual(r["missing"], ["blob_verify"])
        self.assertEqual(self.s.state, "ACTIVE")
        self.assertEqual(self.s.propose("read_file", {"path": "C:/work/docs/a"}, "agent-1")["decision"], "allow")

    def test_empty_or_malformed_evidence_does_not_count(self):
        for ev in ([{"kind": "commit_sha", "ref": ""}, {"kind": "blob_verify", "ref": "x"}], "evidence", None, [5, {"kind": "blob_verify"}]):
            self.assertEqual(self.s.declare_milestone("m1", ev)["code"], "MILESTONE_INCOMPLETE")
        self.assertEqual(self.s.state, "ACTIVE")

    def test_cannot_declare_a_milestone_that_is_not_active(self):
        self.assertEqual(self.reach(self.s, "m2")["code"], "NOT_ACTIVE_MILESTONE")

    def test_complete_declaration_pauses_and_freezes_every_surface(self):
        r = self.s.propose("read_file", {"path": "C:/work/docs/a"}, "agent-1")
        g = self.reach(self.s)
        self.assertEqual(g["state"], "PAUSED_FOR_REVIEW")
        self.assertEqual(self.s.propose("read_file", {"path": "C:/work/docs/a"}, "agent-1")["code"], "PAUSED")
        self.assertEqual(self.s.authorize_execution(r["call_id"], "read_file", {"path": "C:/work/docs/a"}, "harness")["code"], "PAUSED")
        self.assertEqual(self.reach(self.s)["code"], "PAUSED")

    def test_gate_head_is_the_hash_of_the_gate_opened_entry(self):
        g = self.reach(self.s)
        entries = S.Ledger.read(self.s.ledger.path)
        self.assertEqual(entries[-1]["kind"], "gate_opened")
        self.assertEqual(entries[-1]["hash"], g["ledger_head_hash"])

    def test_no_plan_session_has_no_gates(self):
        s = self.open()
        self.assertEqual(s.declare_milestone("m1", [])["code"], "NO_PLAN")

    def test_a_call_from_an_earlier_milestone_cannot_run_later(self):
        r = self.s.propose("read_file", {"path": "C:/work/docs/a"}, "agent-1")
        self.reach(self.s)
        self.s.apply_decision(self.decision(self.s, self.owner))
        self.assertEqual(self.s.authorize_execution(r["call_id"], "read_file", {"path": "C:/work/docs/a"}, "harness")["code"], "OUT_OF_MILESTONE")

    def test_resume_moves_to_the_next_milestone_and_swaps_grants(self):
        self.reach(self.s)
        self.s.apply_decision(self.decision(self.s, self.owner))
        self.assertEqual(self.s.state, "ACTIVE")
        self.assertEqual(self.s.active_milestone()["id"], "m2")
        self.assertEqual(self.s.propose("write_file", {"path": "C:/work/src/a", "content": "x"}, "agent-1")["decision"], "allow")
        self.assertEqual(self.s.propose("read_file", {"path": "C:/work/docs/a"}, "agent-1")["code"], "OUT_OF_MILESTONE")

    def test_completing_the_last_milestone_closes_the_session_without_pass(self):
        self.reach(self.s)
        self.s.apply_decision(self.decision(self.s, self.owner, nonce="n1"))
        self.reach(self.s, "m2")
        out = self.s.apply_decision(self.decision(self.s, self.owner, nonce="n2"))
        self.assertEqual(out["state"], "CLOSED_COMPLETE")
        self.assertEqual(self.s.propose("write_file", {"path": "C:/work/src/a", "content": "x"}, "agent-1")["code"], "SESSION_CLOSED")
        self.assertNotIn("PASS", S.STATES)
        self.assertNotIn('"PASS"', read_text(self.s.ledger.path))

    def test_rework_stays_in_the_milestone_and_a_stop_ends_the_session(self):
        self.reach(self.s)
        self.s.apply_decision(self.decision(self.s, self.owner, decision="rework", nonce="n1"))
        self.assertEqual((self.s.state, self.s.active_milestone()["id"]), ("ACTIVE", "m1"))
        self.reach(self.s)
        self.s.apply_decision(self.decision(self.s, self.owner, decision="stop", nonce="n2"))
        self.assertEqual(self.s.state, "CLOSED_STOPPED")


class TestDecisions(Base):
    def setUp(self):
        super().setUp()
        self.s = self.open(plan=True)
        self.reach(self.s)

    def rejected(self, d, code):
        self.assertEqual(self.code(self.s.apply_decision, d), code)
        self.assertEqual(self.s.state, "PAUSED_FOR_REVIEW")
        last = S.Ledger.read(self.s.ledger.path)[-1]
        self.assertEqual((last["kind"], last["code"]), ("decision_rejected", code))

    def test_signed_owner_decision_is_accepted_and_logged(self):
        self.s.apply_decision(self.decision(self.s, self.owner))
        kinds = [e["kind"] for e in S.Ledger.read(self.s.ledger.path)]
        self.assertIn("decision_accepted", kinds)

    def test_worker_cannot_resume_itself_by_claiming_to_be_the_owner(self):
        d = self.decision(self.s, self.owner)
        d["signature"] = "A" * 86 + "=="
        self.rejected(d, "BAD_SIGNATURE")
        d2 = self.decision(self.s, self.rogue, reviewer_id="owner-michael")
        self.rejected(d2, "BAD_SIGNATURE")

    def test_decided_by_style_claims_without_a_signature_are_nothing(self):
        d = {"session_id": self.s.session_id, "gate_id": self.s.gate["gate_id"], "milestone_id": "m1", "decided_by": "owner",
             "decision": "resume"}
        self.rejected(d, "BAD_DECISION")

    def test_decision_not_in_the_registry(self):
        s = self.open(self.record(plan=True, reviewers=self.reviewers(self.owner)))
        self.reach(s)
        d = self.decision(s, self.verifier_key)
        self.assertEqual(self.code(s.apply_decision, d), "UNKNOWN_REVIEWER")

    def test_whitespace_games_with_the_reviewer_id(self):
        self.rejected(self.decision(self.s, self.owner, reviewer_id="owner-michael "), "UNKNOWN_REVIEWER")

    def test_wrong_session_gate_or_milestone(self):
        self.rejected(self.decision(self.s, self.owner, session_id="other"), "WRONG_GATE")
        self.rejected(self.decision(self.s, self.owner, gate_id="g-m2"), "WRONG_GATE")
        self.rejected(self.decision(self.s, self.owner, milestone_id="m2"), "WRONG_GATE")

    def test_stale_ledger_head(self):
        self.rejected(self.decision(self.s, self.owner, ledger_head_hash="0" * 64), "STALE_LEDGER_HEAD")

    def test_a_decision_for_an_earlier_gate_cannot_be_replayed_on_a_later_one(self):
        old = self.decision(self.s, self.owner, decision="rework", nonce="n1")
        self.s.apply_decision(old)
        self.reach(self.s)
        self.assertEqual(self.code(self.s.apply_decision, old), "STALE_LEDGER_HEAD")

    def test_tampering_after_signing(self):
        d = self.decision(self.s, self.owner, decision="resume")
        d["decision"] = "stop"
        self.rejected(d, "BAD_SIGNATURE")

    def test_nonce_cannot_be_reused(self):
        self.s.apply_decision(self.decision(self.s, self.owner, decision="rework", nonce="same"))
        self.reach(self.s)
        self.rejected(self.decision(self.s, self.owner, nonce="same"), "NONCE_REPLAY")

    def test_forged_decision_does_not_burn_the_nonce(self):
        bad = self.decision(self.s, self.owner, nonce="keep")
        bad["signature"] = "A" * 86 + "=="
        self.assertEqual(self.code(self.s.apply_decision, bad), "BAD_SIGNATURE")
        self.s.apply_decision(self.decision(self.s, self.owner, nonce="keep"))
        self.assertEqual(self.s.state, "ACTIVE")

    def test_expired_decision(self):
        d = self.decision(self.s, self.owner)
        self.clock.advance(hours=2)
        self.rejected(d, "DECISION_EXPIRED")

    def test_bad_decision_value_and_missing_fields(self):
        self.rejected(self.decision(self.s, self.owner, decision="approve"), "BAD_DECISION")
        d = self.decision(self.s, self.owner)
        del d["nonce"]
        self.rejected(d, "BAD_DECISION")
        self.assertEqual(self.code(self.s.apply_decision, "resume"), "BAD_DECISION")

    def test_decision_when_nothing_is_paused(self):
        s = self.open(plan=True)
        with self.assertRaises(S.AuthorityError) as cm:
            s.apply_decision({"x": 1})
        self.assertEqual(cm.exception.code, "NOT_PAUSED")

    def test_icarus_can_review_delegated_work(self):
        self.s.apply_decision(self.decision(self.s, self.icarus))
        self.assertEqual(self.s.state, "ACTIVE")

    def test_independent_verifier_can_review(self):
        self.s.apply_decision(self.decision(self.s, self.verifier_key))
        self.assertEqual(self.s.active_milestone()["id"], "m2")

    def test_the_executor_cannot_approve_its_own_work(self):
        s = self.open(self.record(plan=True, executor_id="verifier-1"))
        self.reach(s)
        self.assertEqual(self.code(s.apply_decision, self.decision(s, self.verifier_key)), "SELF_APPROVAL")

    def test_anyone_who_acted_in_the_session_cannot_approve_it(self):
        s = self.open(self.record(plan=True))
        s.propose("read_file", {"path": "C:/work/docs/a"}, "verifier-1")
        self.assertIn("verifier-1", s.actors)
        self.reach(s)
        self.assertEqual(self.code(s.apply_decision, self.decision(s, self.verifier_key)), "SELF_APPROVAL")
        s.apply_decision(self.decision(s, self.owner))
        self.assertEqual(s.state, "ACTIVE")

    def test_denied_attempts_do_not_make_someone_an_actor(self):
        s = self.open(self.record(plan=True))
        s.propose("shell", {}, "verifier-1")
        self.assertNotIn("verifier-1", s.actors)

    def test_issuer_is_not_an_actor_so_icarus_can_review_what_he_delegated(self):
        s = self.open(self.record(plan=True))
        self.assertNotIn("icarus", s.actors)

    def test_icarus_cannot_approve_his_own_work(self):
        rec = self.record(issued_by="charter", signer_id="icarus", executor_id="icarus")
        rec["grants"] = {"tools": ["read_file"], "path_scopes": ["C:/work/icarus-own"], "max_calls": 5, "expires_at": "2026-11-05T00:00:00Z", "spend_eur": 0}
        ms = [{"id": "m1", "goal": "own work", "grants": {"tools": ["read_file"], "path_scopes": ["C:/work/icarus-own"]}, "evidence_required": ["blob_verify"]}]
        rec["checkpoint_plan"] = self.plan(milestones=ms)
        s = self.open(rec)
        s.declare_milestone("m1", [{"kind": "blob_verify", "ref": "x"}])
        self.assertEqual(self.code(s.apply_decision, self.decision(s, self.icarus)), "SELF_APPROVAL")
        s.apply_decision(self.decision(s, self.owner, nonce="o1"))
        self.assertEqual(s.state, "CLOSED_COMPLETE")

    def test_an_independent_verifier_can_approve_icarus_own_work(self):
        rec = self.record(issued_by="owner", signer_id="owner-michael", executor_id="icarus", checkpoint_plan=self.plan(approved_by="owner-michael"))
        s = self.open(rec, signer=self.owner)
        self.assertTrue(s.independent_required)
        self.reach(s)
        s.apply_decision(self.decision(s, self.verifier_key))
        self.assertEqual(s.active_milestone()["id"], "m2")

    def test_another_adjudicator_cannot_approve_icarus_own_work(self):
        icarus2 = Key("icarus-2", "adjudicator")
        ch = self.make_charter(principals=[self.owner.principal(), self.icarus.principal(), icarus2.principal(), self.verifier_key.principal()])
        rec = self.record(issued_by="owner", signer_id="owner-michael", executor_id="icarus", checkpoint_plan=self.plan(approved_by="owner-michael"),
                          reviewers=self.reviewers(icarus2, self.owner))
        s = self.open(rec, signer=self.owner, charter=ch)
        self.reach(s)
        self.assertEqual(self.code(s.apply_decision, self.decision(s, icarus2)), "INDEPENDENCE_REQUIRED")

    def test_gate_stays_closed_when_the_verifier_disappears(self):
        v = S.Ed25519Verifier()
        s = self.open(plan=True, verifier=v)
        self.reach(s)
        d = self.decision(s, self.owner)
        v.available = False
        self.assertEqual(self.code(s.apply_decision, d), "BLOCKED_NO_VERIFIER")
        self.assertEqual(s.state, "PAUSED_FOR_REVIEW")
        self.assertIn("gate_blocked", [e["kind"] for e in S.Ledger.read(s.ledger.path)])
        v.available = True
        s.apply_decision(d)
        self.assertEqual(s.state, "ACTIVE")


class TestWholeStory(Base):
    def test_owner_sets_boundaries_icarus_delegates_agent_works_gates_hold(self):
        s = self.open(plan=True)
        r = s.propose("read_file", {"path": "C:/work/docs/spec.md"}, "agent-1")
        self.assertEqual(s.authorize_execution(r["call_id"], "read_file", {"path": "C:/work/docs/spec.md"}, "harness")["decision"], "allow")
        s.record_result(r["call_id"], "spec text")
        self.assertEqual(s.propose("write_file", {"path": "C:/work/src/x", "content": "y"}, "agent-1")["code"], "OUT_OF_MILESTONE")
        self.reach(s)
        self.assertEqual(s.propose("read_file", {"path": "C:/work/docs/spec.md"}, "agent-1")["code"], "PAUSED")
        forged = self.decision(s, self.rogue, reviewer_id="icarus")
        self.assertEqual(self.code(s.apply_decision, forged), "BAD_SIGNATURE")
        s.apply_decision(self.decision(s, self.icarus, nonce="i1"))
        r2 = s.propose("write_file", {"path": "C:/work/src/x", "content": "y"}, "agent-1")
        self.assertEqual(r2["decision"], "allow")
        self.assertEqual(s.spent_eur, 0)
        ok, msg = S.Ledger.verify(s.ledger.path)
        self.assertTrue(ok, msg)


if __name__ == "__main__":
    unittest.main()
