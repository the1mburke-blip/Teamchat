"""Tests for icarus/primitives (ledger, runner, reasoner, verify). No network."""
import hashlib
import http.server
import json
import sys
import threading

import pytest

from icarus.primitives.ledger import BLOCKED, DONE, QUEUED, Ledger, LedgerError
from icarus.primitives.reasoner import (FakeReasoner, OpenAICompatReasoner,
                                        ReasonerError, parse_plan)
from icarus.primitives.runner import run_once
from icarus.primitives.verify import verify

PY = sys.executable
PLAN_OK = json.dumps({
    "files": [{"path": "make.py", "content": "open('out.txt','w').write('hello')\n"}],
    "commands": [[PY, "make.py"]],
})
SPEC = {"expected_files": ["out.txt"],
        "sha256": {"out.txt": hashlib.sha256(b"hello").hexdigest()},
        "allowed_commands": [__import__("pathlib").Path(PY).name]}


def enqueue(root, job_id="j1", spec=SPEC, max_attempts=3):
    led = Ledger(root)
    led.enqueue(job_id, {"objective": "write hello"}, spec, author="owner",
                max_attempts=max_attempts)
    led.close()


# ---- ledger ---------------------------------------------------------------
def test_enqueue_requires_verify_spec(tmp_path):
    led = Ledger(tmp_path)
    with pytest.raises(LedgerError):
        led.enqueue("j", {"x": 1}, {}, author="owner")


def test_claim_is_exclusive(tmp_path):
    enqueue(tmp_path)
    a, b = Ledger(tmp_path), Ledger(tmp_path)
    assert a.claim("A") is not None
    assert b.claim("B") is None


def test_expired_lease_is_reclaimable(tmp_path):
    enqueue(tmp_path)
    led = Ledger(tmp_path)
    assert led.claim("A", lease_seconds=-1)["claimed_by"] == "A"
    assert led.claim("B")["claimed_by"] == "B"


def test_settle_requires_holder_and_receipt(tmp_path):
    enqueue(tmp_path)
    led = Ledger(tmp_path)
    led.claim("A")
    with pytest.raises(LedgerError):
        led.settle("j1", "B", {"verifier": "v", "verdict": "PASS"})
    with pytest.raises(LedgerError):
        led.settle("j1", "A", {"verdict": "PASS"})


def test_run_log_chain_detects_tampering(tmp_path):
    enqueue(tmp_path)
    led = Ledger(tmp_path)
    led.append({"type": "note", "msg": "a"})
    assert led.verify_chain()
    lines = led.log_path.read_text().splitlines()
    rec = json.loads(lines[-1]); rec["msg"] = "edited"
    lines[-1] = json.dumps(rec, sort_keys=True)
    led.log_path.write_text("\n".join(lines) + "\n")
    assert not led.verify_chain()


# ---- reasoner -------------------------------------------------------------
@pytest.mark.parametrize("bad", ["not json", "[]", '{"commands": "ls"}',
                                 '{"commands": [[]]}', '{"files": [{"path": 1}]}'])
def test_parse_plan_rejects_bad_shapes(bad):
    with pytest.raises(ReasonerError):
        parse_plan(bad)


def test_openai_compat_requires_config(monkeypatch):
    monkeypatch.delenv("ICARUS_REASONER_URL", raising=False)
    monkeypatch.delenv("ICARUS_REASONER_MODEL", raising=False)
    with pytest.raises(ReasonerError):
        OpenAICompatReasoner()


def test_openai_compat_against_local_stub():
    seen = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen["auth"] = self.headers.get("Authorization")
            out = json.dumps({"choices": [{"message": {"content": PLAN_OK}}]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(out)))
            self.end_headers(); self.wfile.write(out)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        r = OpenAICompatReasoner(f"http://127.0.0.1:{srv.server_port}/v1", "m", api_key="k")
        plan = r.plan({"objective": "x"})
    finally:
        srv.shutdown()
    assert plan["commands"] == [[PY, "make.py"]]
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["auth"] == "Bearer k"


# ---- verify ---------------------------------------------------------------
def _exec(code=0, valid=True, argv=None, out=""):
    return {"plan_valid": valid, "git_sha": None, "error": None,
            "commands": [{"argv": argv or [PY, "make.py"], "exit_code": code,
                          "stdout": out, "stderr": ""}]}


def test_verify_pass(tmp_path):
    (tmp_path / "out.txt").write_text("hello")
    r = verify(tmp_path, SPEC, _exec())
    assert r["verdict"] == "PASS" and r["verifier"]


@pytest.mark.parametrize("case", ["missing", "exit", "sha", "secret", "cmd", "schema", "git"])
def test_verify_fails(tmp_path, case):
    spec = dict(SPEC)
    ex = _exec()
    if case != "missing":
        (tmp_path / "out.txt").write_text("hello" if case != "sha" else "HELLO")
    if case == "exit":
        ex = _exec(code=1)
    if case == "secret":
        ex = _exec(out="token ghp_" + "a" * 36)
    if case == "cmd":
        ex = _exec(argv=["rm", "-rf", "x"])
    if case == "schema":
        ex = _exec(valid=False)
    if case == "git":
        spec["require_git_sha"] = True
    r = verify(tmp_path, spec, ex)
    assert r["verdict"] == "FAIL"
    gate2 = case in ("secret", "cmd", "schema")
    assert r["gate_2_policy"]["pass"] is (not gate2)


# ---- runner end to end ----------------------------------------------------
def test_run_once_pass(tmp_path):
    enqueue(tmp_path)
    out = run_once(tmp_path, FakeReasoner([PLAN_OK]), "laptop")
    assert out["status"] == DONE and out["receipt"]["verdict"] == "PASS"
    led = Ledger(tmp_path)
    assert led.get("j1")["status"] == DONE
    assert led.verify_chain()
    assert (tmp_path / "jobs/j1/attempt-1/receipt.json").is_file()


def test_run_once_idle(tmp_path):
    assert run_once(tmp_path, FakeReasoner([]), "laptop") == {"status": "idle"}


def test_failures_requeue_then_block(tmp_path):
    enqueue(tmp_path, max_attempts=2)
    r = FakeReasoner(["not json", "still not json"])
    assert run_once(tmp_path, r, "x")["status"] == QUEUED
    assert run_once(tmp_path, r, "x")["status"] == BLOCKED
    assert run_once(tmp_path, r, "x") == {"status": "idle"}


def test_disallowed_command_vetoed_before_execution(tmp_path):
    enqueue(tmp_path)
    plan = json.dumps({"files": [], "commands": [["sh", "-c", "touch pwned"]]})
    out = run_once(tmp_path, FakeReasoner([plan]), "x")
    assert out["receipt"]["verdict"] == "FAIL"
    assert not list(tmp_path.rglob("pwned"))


def test_path_escape_rejected(tmp_path):
    enqueue(tmp_path)
    plan = json.dumps({"files": [{"path": "../../escape.txt", "content": "x"}], "commands": []})
    out = run_once(tmp_path, FakeReasoner([plan]), "x")
    assert out["receipt"]["verdict"] == "FAIL"
    assert not list(tmp_path.parent.rglob("escape.txt"))


def test_openai_compat_waits_out_rate_limit_then_succeeds():
    calls = {"n": 0}

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            calls["n"] += 1
            if calls["n"] == 1:
                self.send_response(429); self.send_header("Content-Length", "0"); self.end_headers()
                return
            out = json.dumps({"choices": [{"message": {"content": PLAN_OK}}]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(out)))
            self.end_headers(); self.wfile.write(out)

        def log_message(self, *a):
            pass

    slept = []
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        r = OpenAICompatReasoner(f"http://127.0.0.1:{srv.server_port}/v1", "m", api_key="k",
                                 sleep=slept.append)
        plan = r.plan({"objective": "x"})
    finally:
        srv.shutdown()
    assert plan["commands"] == [[PY, "make.py"]] and calls["n"] == 2 and slept == [90]


def test_openai_compat_persistent_rate_limit_is_a_reasoner_error():
    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(429); self.send_header("Content-Length", "0"); self.end_headers()

        def log_message(self, *a):
            pass

    slept = []
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        r = OpenAICompatReasoner(f"http://127.0.0.1:{srv.server_port}/v1", "m", sleep=slept.append)
        with pytest.raises(ReasonerError, match="HTTP 429"):
            r.plan({"objective": "x"})
    finally:
        srv.shutdown()
    assert slept == [90, 90]
