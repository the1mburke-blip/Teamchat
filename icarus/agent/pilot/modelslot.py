"""The model slot: an OpenAI-compatible endpoint where Icarus, not the harness's model, answers.

A harness pointed at this endpoint believes it is talking to a model. It is talking to Icarus Core:
every request goes  token -> Session (live_ready?) -> GovernedCore.step() -> reasoner.
This module never holds a reasoner and never calls one. The only route to a model is core.step(), and the
Core here is built with a NullHand, so nothing in this path can execute a tool: the harness executes, and only
what the Session authorized (see session.py) at the hook.

Rules this module enforces (contract section 3):
- loopback only, a bearer token per session, bodies capped;
- a session that is not live_ready (no kernel, no signature verifier, broken ledger) is refused at registration
  and again on every request;
- the request is written to the ledger BEFORE the reasoner is asked (intake is durable before work starts);
- a tool call is returned only if the tool was offered in the request AND the Session authorizes it;
- a tool result the harness sends is evidence of what the harness says, never independent proof;
- a final answer is never reported as PASS unless an independent adjudicator confirmed it.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ..governed import GovernedCore, NullHand
from .session import AuthorityError, LedgerError, canonical, sha256_hex

MODEL_ID = "icarus"
MAX_BODY = 1_048_576
ROLES_OK = ("system", "user", "assistant", "tool")
# Session denials that end the task instead of being worked around (the reasoner cannot fix them).
HARD_CODES = frozenset({"MAX_CALLS", "SPEND_EXCEEDED", "SESSION_EXPIRED", "SESSION_CLOSED", "PAUSED"})


class GovernedKernelAdapter:
    """Lets the Session consult the real GovernedKernel. Proposal time counts and logs (authorize); execution time
    only re-reads the decision (decide), so a call spends the kernel's budget once."""

    accepts_phase = True

    def __init__(self, kernel, grant, name="GovernedKernel"):
        self.kernel, self.grant, self.name = kernel, grant, name

    def __call__(self, tool, args, phase="proposal"):
        d = self.kernel.authorize(self.grant, tool, args) if phase == "proposal" else self.kernel.decide(self.grant, tool, args)
        return d.allowed, d.reason


def error_body(etype, code, message, session_id=None, seq=None, owner_action="", evidence=()):
    return {"error": {"message": message, "type": etype, "code": code},
            "icarus": {"session_id": session_id, "ledger_seq": seq, "owner_action": owner_action, "evidence": list(evidence)}}


def sse_lines(completion):
    """Replay a finished, authorized completion as server-sent events (governed output cannot be streamed before
    it is authorized)."""
    ch = completion["choices"][0]
    msg, base = ch["message"], {"id": completion["id"], "object": "chat.completion.chunk", "created": completion["created"], "model": completion["model"]}
    first_delta = {"role": "assistant"}
    if msg.get("tool_calls"):
        first_delta["content"] = None
        first_delta["tool_calls"] = [dict(tc, index=i) for i, tc in enumerate(msg["tool_calls"])]
    else:
        first_delta["content"] = msg.get("content")
    chunks = [dict(base, choices=[{"index": 0, "delta": first_delta, "finish_reason": None}]),
              dict(base, choices=[{"index": 0, "delta": {}, "finish_reason": ch["finish_reason"]}])]
    return [f"data: {json.dumps(c)}\n\n" for c in chunks] + ["data: [DONE]\n\n"]


class _Binding:
    def __init__(self, session, state, token_sha):
        self.session, self.state, self.token_sha = session, state, token_sha
        self.pending = {}  # call_id -> {"tool", "args"} proposed, result not yet recorded
        self.recorded = set()
        self.unmatched = set()
        self.last_payload = None  # replayed if the harness repeats a request while a call is unanswered
        self.final = None
        self.lock = threading.RLock()


class SlotRuntime:
    def __init__(self, core, clock=time.time):
        if not isinstance(core, GovernedCore):
            raise TypeError("the slot needs a GovernedCore")
        if not isinstance(core.hand, NullHand):
            raise AuthorityError("CORE_NOT_HARNESS_MODE", "the slot's Core must be built with a NullHand; only the harness executes")
        self._core = core
        self._clock = clock
        self._by_token = {}
        self._by_session = {}
        self.rejected = []  # requests refused before any session was identified

    # ------------------------------------------------------------ registration
    def register(self, session, task, grant, preflight):
        """Bind a live session to this endpoint. Returns the bearer token for the harness profile."""
        if session.execution != "harness":
            raise AuthorityError("CORE_MODE_NOT_IMPLEMENTED", "the slot serves harness-mode sessions only; core mode is not built")
        if not session.live_ready:
            raise AuthorityError("NOT_LIVE_READY", "the live endpoint refuses a session without a kernel, a signature verifier and a writable ledger")
        if session.state != "ACTIVE":
            raise AuthorityError("SESSION_NOT_ACTIVE", session.state)
        if getattr(session.kernel_check, "kernel", None) is not self._core.kernel:
            raise AuthorityError("KERNEL_MISMATCH", "the session's kernel is not this Core's kernel")
        if grant.task_id != session.task_id:
            raise AuthorityError("TASK_MISMATCH", "kernel grant and session are for different tasks")
        if session.session_id in self._by_session:
            raise AuthorityError("ALREADY_REGISTERED", session.session_id)
        state = self._core.begin(task, grant, preflight)
        if state.done:
            raise AuthorityError("PREFLIGHT_BLOCKED", "; ".join(state.outcome.reasons))
        token = secrets.token_urlsafe(32)
        b = _Binding(session, state, sha256_hex(token.encode()))
        self._by_token[b.token_sha] = b
        self._by_session[session.session_id] = b
        session.log_event("slot", "slot_registered", kernel=session.kernel_name, task_sha256=sha256_hex(task.encode()))
        return token

    def _lookup(self, token):
        if not isinstance(token, str) or not token:
            return None
        return self._by_token.get(sha256_hex(token.encode()))

    # ------------------------------------------------------------ endpoints
    def models(self, token):
        if self._lookup(token) is None:
            self.rejected.append("auth")
            return 401, error_body("auth", "UNAUTHORIZED", "invalid token")
        return 200, {"object": "list", "data": [{"id": MODEL_ID, "object": "model", "owned_by": "icarus"}]}

    def handle_chat(self, token, body):
        """Returns (http_status, payload). Every refusal below happens before the reasoner is asked."""
        b = self._lookup(token)
        if b is None:
            self.rejected.append("auth")
            return 401, error_body("auth", "UNAUTHORIZED", "invalid token")
        with b.lock:
            try:
                return self._chat(b, body)
            except LedgerError as e:
                return 503, error_body("icarus_blocked", "BLOCKED", "the ledger cannot be written, so nothing is answered",
                                       b.session.session_id, None, evidence=[e.code])

    # ------------------------------------------------------------ internals
    def _refuse(self, b, status, etype, code, message, evidence=()):
        sess = b.session
        try:
            e = sess.log_event("slot", "slot_request_denied", decision="deny", code=code, reason=message)
            seq = e["seq"]
        except LedgerError:
            seq = None
        return status, error_body(etype, code, message, sess.session_id, seq, evidence=evidence)

    @staticmethod
    def _validate(body):
        if not isinstance(body, dict):
            return "body must be a JSON object"
        msgs = body.get("messages")
        if not isinstance(msgs, list) or not msgs:
            return "messages must be a non-empty list"
        for m in msgs:
            if not isinstance(m, dict) or m.get("role") not in ROLES_OK:
                return "each message needs a role of system, user, assistant or tool"
            if m.get("content") is not None and not isinstance(m["content"], str):
                return "message content must be a string"
            if m["role"] == "tool" and not isinstance(m.get("tool_call_id"), str):
                return "a tool message needs a tool_call_id"
        tools = body.get("tools", [])
        if not isinstance(tools, list):
            return "tools must be a list"
        for t in tools:
            fn = t.get("function") if isinstance(t, dict) else None
            if not isinstance(fn, dict) or t.get("type") != "function" or not isinstance(fn.get("name"), str) or not fn["name"]:
                return "each tool must be {type: function, function: {name, ...}}"
        if "stream" in body and not isinstance(body["stream"], bool):
            return "stream must be a boolean"
        if body.get("n", 1) != 1:
            return "only n=1 is served"
        return None

    def _completion(self, b, message, finish_reason, seq, extra=None):
        out = {"id": f"icarus-{seq:04d}", "object": "chat.completion", "created": int(self._clock()), "model": MODEL_ID,
               "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
               "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
               "icarus": {"session_id": b.session.session_id, "ledger_seq": seq}}
        if extra:
            out["icarus"].update(extra)
        return out

    @staticmethod
    def _outward(result):
        """The text the harness sees. Nothing leaves here as PASS unless an independent adjudicator confirmed it."""
        lines = result.report().split("\n")
        status = result.status
        if status == "PASS" and result.independence != "kernel+adjudicator":
            status = "PARTIAL"
            lines.insert(1, "note: verified by the kernel only; independent adjudication is outstanding, so this is not reported as PASS")
        lines[0] = f"RESULT: {status} task={result.task_id}"
        return status, "\n".join(lines)

    def _chat(self, b, body):
        sess, core = b.session, self._core
        if not sess.live_ready:
            return self._refuse(b, 503, "icarus_blocked", "NOT_LIVE_READY", "this session is not live ready (kernel, verifier or ledger)")
        if sess.state == "PAUSED_FOR_REVIEW":
            return self._refuse(b, 409, "icarus_paused", "PAUSED_FOR_REVIEW", "a review gate is open")
        if sess.state != "ACTIVE":
            return self._refuse(b, 409, "icarus_closed", "SESSION_CLOSED", sess.state)
        problem = self._validate(body)
        if problem:
            return self._refuse(b, 400, "bad_request", "BAD_REQUEST", problem)
        msgs = body["messages"]
        # durable intake first: the request is on the ledger before any work starts
        intake = sess.log_event("slot", "slot_request", request_sha256=sha256_hex(canonical(body)), n_messages=len(msgs),
                                n_tools=len(body.get("tools", [])), stream=bool(body.get("stream", False)))
        if b.final is not None:
            return 200, self._completion(b, {"role": "assistant", "content": b.final}, "stop", intake["seq"], {"replayed": True})
        # tool results the harness reports (evidence of what the harness says, not independent proof)
        observations, new_results = [], 0
        for m in msgs:
            if m["role"] != "tool":
                continue
            cid, content = m["tool_call_id"], m.get("content") or ""
            if cid in b.recorded:
                continue
            if cid not in b.pending:
                if cid not in b.unmatched:
                    b.unmatched.add(cid)
                    sess.record_result(cid, content)  # logged as unmatched, never trusted
                continue
            call, prop = sess.calls[cid], b.pending[cid]
            new_results += 1
            if call["state"] == "EXECUTED":
                sess.record_result(cid, content)
                ok = True
                try:
                    parsed = json.loads(content)
                    ok = not (isinstance(parsed, dict) and parsed.get("ok") is False)
                except ValueError:
                    pass
                observations.append({"kind": "result", "tool": prop["tool"], "args": prop["args"], "content": content, "ok": ok, "error": "the tool reported failure"})
            else:
                # the harness reports a result for a call Icarus never authorized for execution
                sess.log_event("slot", "ungoverned_result_reported", call_id=cid, call_state=call["state"],
                               content_sha256=sha256_hex(content.encode()), reason="result for a call that was never authorized at the hook")
                observations.append({"kind": "result", "tool": prop["tool"], "args": prop["args"], "content": "", "ok": False,
                                     "error": "not authorized for execution; the reported result is not trusted"})
            b.recorded.add(cid)
            del b.pending[cid]
        # a call that can no longer run (burned at the hook, or left over from an earlier milestone) is dropped as a failure
        active_id = sess.active_milestone()["id"] if sess.milestones else None
        for cid in list(b.pending):
            call = sess.calls[cid]
            if call["state"] == "BURNED" or call["milestone"] != active_id:
                prop = b.pending.pop(cid)
                b.recorded.add(cid)
                sess.log_event("slot", "pending_call_dropped", call_id=cid, call_state=call["state"], reason="can no longer be executed")
                observations.append({"kind": "result", "tool": prop["tool"], "args": prop["args"], "content": "", "ok": False,
                                     "error": "the proposed call can no longer be executed (burned, or from an earlier milestone)"})
        if b.pending and not new_results and b.last_payload is not None:
            return 200, b.last_payload  # the harness repeated itself while a call is unanswered: replay, no model call
        # offered tools: named in the request AND in the session's active grant
        granted = set(sess.active_grants().get("tools", []))
        offered = {}
        for t in body.get("tools", []):
            fn = t["function"]
            if fn["name"] in granted:
                offered[fn["name"]] = str(fn.get("description", ""))[:300]
        context = ""
        for m in reversed(msgs):
            if m["role"] == "user" and m.get("content"):
                context = m["content"]
                break

        def authorizer(tool, args):
            if tool not in offered:
                sess.log_event("slot", "proposal_filtered", tool=str(tool)[:80], reason="not offered in this request or not in the active grant")
                return False, f"TOOL_NOT_OFFERED: {str(tool)[:60]} is not available here", {}
            r = sess.propose(tool, args, actor=sess.executor_id)
            if r["decision"] == "allow":
                return True, "granted", {"call_id": r["call_id"], "args_sha256": r["args_sha256"]}
            return False, f"{r['code']}: {r['reason']}", {"hard": r["code"] in HARD_CODES, "code": r["code"]}

        out = core.step(b.state, observations, tools=offered, context=context, authorizer=authorizer)
        if out.kind == "tool":
            cid = out.meta["call_id"]
            b.pending[cid] = {"tool": out.tool, "args": out.args}
            seq = sess.log_event("slot", "slot_response", finish_reason="tool_calls", call_id=cid, tool=out.tool)["seq"]
            msg = {"role": "assistant", "content": None, "tool_calls": [
                {"id": cid, "type": "function", "function": {"name": out.tool, "arguments": json.dumps(out.args, sort_keys=True)}}]}
            payload = self._completion(b, msg, "tool_calls", seq, {"call_state": "AUTHORIZED"})
            b.last_payload = payload
            return 200, payload
        if out.kind == "finish":
            status, text = self._outward(out.result)
            b.final = text
            seq = sess.log_event("slot", "slot_final", outward_status=status, independence=out.result.independence)["seq"]
            return 200, self._completion(b, {"role": "assistant", "content": text}, "stop", seq)
        res = out.result
        seq = sess.log_event("slot", "slot_blocked", reasons=list(res.reasons)[:6], owner_action=res.owner_action)["seq"]
        return 503, error_body("icarus_blocked", "BLOCKED", "; ".join(res.reasons)[:300], sess.session_id, seq,
                               owner_action=res.owner_action, evidence=list(res.reasons)[:6])


def _make_handler(runtime):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "icarus-slot"

        def log_message(self, *a):  # no access log: nothing here may print a token
            pass

        def _send(self, status, payload=None, lines=None):
            if lines is not None:
                data = "".join(lines).encode("utf-8")
                ctype = "text/event-stream"
            else:
                data = json.dumps(payload).encode("utf-8")
                ctype = "application/json"
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)
            self.close_connection = True

        def _token(self):
            h = self.headers.get("Authorization", "")
            return h[7:].strip() if h.lower().startswith("bearer ") else ""

        def _fail(self, status, code, message):
            runtime.rejected.append(code)
            self._send(status, error_body("bad_request" if status < 500 else "server_error", code, message))

        def do_GET(self):
            if self.path != "/v1/models":
                return self._fail(404, "NOT_FOUND", "unknown path")
            status, payload = runtime.models(self._token())
            self._send(status, payload)

        def do_POST(self):
            if self.path != "/v1/chat/completions":
                return self._fail(404, "NOT_FOUND", "unknown path")
            ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if ctype != "application/json":
                return self._fail(415, "UNSUPPORTED_MEDIA_TYPE", "send application/json")
            try:
                n = int(self.headers.get("Content-Length", ""))
            except ValueError:
                return self._fail(411, "LENGTH_REQUIRED", "Content-Length is required")
            if n < 0 or n > MAX_BODY:
                return self._fail(413, "BODY_TOO_LARGE", f"limit is {MAX_BODY} bytes")
            raw = self.rfile.read(n)
            try:
                body = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return self._fail(400, "BAD_JSON", "body is not valid JSON")
            try:
                status, payload = runtime.handle_chat(self._token(), body)
            except Exception:  # fail closed, say nothing about internals
                runtime.rejected.append("internal")
                return self._send(500, error_body("server_error", "INTERNAL", "request failed closed"))
            if status == 200 and isinstance(body, dict) and body.get("stream") is True:
                return self._send(200, lines=sse_lines(payload))
            self._send(status, payload)

        def _no(self):
            self._fail(405, "METHOD_NOT_ALLOWED", "only GET /v1/models and POST /v1/chat/completions")

        do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = _no

    return Handler


class SlotServer:
    """Loopback HTTP front for a SlotRuntime."""

    def __init__(self, runtime, host="127.0.0.1", port=0):
        if host not in ("127.0.0.1", "::1"):
            raise ValueError("the model slot binds loopback only")
        self.runtime = runtime
        self.httpd = ThreadingHTTPServer((host, port), _make_handler(runtime))
        self.httpd.daemon_threads = True
        self._thread = None

    @property
    def base_url(self):
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}/v1"

    def start(self):
        self._thread = threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        if self._thread:
            self._thread.join(timeout=5)
