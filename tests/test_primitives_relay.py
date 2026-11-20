"""Daemon early verdict notice. No network: the poster and urlopen are faked."""
import io
import json
import re

from icarus.primitives.daemon import early_notice
from icarus.primitives.relay import PREFIX, notice_body, post_notice

RECEIPT = {"verifier": "icarus.primitives.verify/v1", "verdict": "PASS",
           "gate_1_technical": {"pass": True, "reasons": []},
           "gate_2_policy": {"pass": True, "reasons": []}}

# Copied from icarus/athena-gas/Athena.gs: the notice must never trigger Athena.
OWN_OUTPUT = re.compile(r"^\s*(# Icarus run|\[ICARUS via runtime\]|\[ICARUS ADJUDICATION\]|\[TEAMCHAT_WAKE\])")
ADDRESSED = re.compile(r"\[TO\]\s*\[(ICARUS|ATHENA)\]|(^|[^\w@])@(icarus|athena)\b", re.I)
CLAIM_PASS = re.compile(r"^[ \t>*-]*(?:\[STATUS\]\s*PASS\b|STATUS\s*:\s*PASS\b|/evidence\s+\S+\s+PASS\b)", re.I | re.M)


class FakeLedger:
    def __init__(self, issue=237, attempts=1):
        self.issue, self.attempts = issue, attempts

    def job(self, job_id):
        return {"task": {"source_issue": self.issue}, "state": {"attempts": self.attempts}}


def test_body_is_ignored_by_athena_and_not_the_canonical_relay():
    b = notice_body("canary-008", "done", RECEIPT, 1, "2026-11-18T23:00:00Z")
    assert b.startswith(PREFIX) and OWN_OUTPUT.match(b)
    assert not ADDRESSED.search(b) and not CLAIM_PASS.search(b)
    assert "Ledger job" not in b and "PASS" in b and "not self-awarded" in b


def test_reasons_included_on_fail():
    r = {**RECEIPT, "verdict": "FAIL", "gate_1_technical": {"pass": False, "reasons": ["missing file: x"]}}
    assert "missing file: x" in notice_body("j", "BLOCKER_DISCOVERED", r, 2, "t")


def test_posts_final_outcomes_to_source_issue(monkeypatch):
    monkeypatch.setenv("TARGET_REPO", "o/r")
    monkeypatch.setenv("GH_TOKEN", "t")
    calls = []
    poster = lambda repo, tok, issue, body: calls.append((repo, issue, body)) or True
    out = {"status": "done", "job": "canary-008", "receipt": RECEIPT}
    assert early_notice(FakeLedger(), out, poster) is True
    assert calls[0][0] == "o/r" and calls[0][1] == 237 and "canary-008" in calls[0][2]


def test_skips_non_final_disabled_and_issueless(monkeypatch):
    poster = lambda *a: (_ for _ in ()).throw(AssertionError("must not post"))
    assert early_notice(FakeLedger(), {"status": "queued", "job": "j", "receipt": RECEIPT}, poster) is None
    assert early_notice(FakeLedger(), {"status": "idle"}, poster) is None
    assert early_notice(FakeLedger(issue=0), {"status": "done", "job": "j", "receipt": RECEIPT}, poster) is None
    monkeypatch.setenv("ICARUS_EARLY_RELAY", "0")
    assert early_notice(FakeLedger(), {"status": "done", "job": "j", "receipt": RECEIPT}, poster) is None


class Resp(io.BytesIO):
    def __init__(self, status):
        super().__init__(b"{}")
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_post_notice_request_and_failures():
    seen = {}

    def opener(req, timeout):
        seen.update(url=req.full_url, auth=req.get_header("Authorization"), body=json.loads(req.data))
        return Resp(201)

    assert post_notice("o/r", "tok", 237, "hi", opener) is True
    assert seen["url"].endswith("/repos/o/r/issues/237/comments") and seen["auth"] == "Bearer tok"
    assert seen["body"] == {"body": "hi"}

    def boom(req, timeout):
        raise OSError("network down")

    assert post_notice("o/r", "tok", 237, "hi", boom) is False
    assert post_notice("", "tok", 237, "hi", opener) is False
    assert post_notice("o/r", "", 237, "hi", opener) is False
