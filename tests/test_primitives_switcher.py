"""Model switcher: rotate on rate limits with the task intact, pool break + reset, auth = owner stop."""
import json
from pathlib import Path

import pytest

from icarus.primitives.reasoner import ReasonerError, ReasonerHTTPError
from icarus.primitives.switcher import ModelSwitcher, OwnerAuthError, load_pool

ROOT = Path(__file__).resolve().parents[1]
PLAN = {"commands": [], "files": [], "notes": "ok"}


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def scripted(script, seen):
    """script: {model: [outcome, ...]} where outcome is a plan dict, an int HTTP code, or 'bad'."""
    class R:
        def __init__(self, e):
            self.m = e["model"]

        def plan(self, task):
            seen.append((self.m, json.dumps(task, sort_keys=True)))
            out = script[self.m].pop(0)
            if isinstance(out, dict):
                return out
            if out == "bad":
                raise ReasonerError("reasoner returned invalid JSON")
            raise ReasonerHTTPError(out, f"{self.m}: HTTP {out}")
    return lambda e, ident="": R(e)


POOL = [{"model": m, "base": "b", "key": "k"} for m in ("a", "b", "c")]


def test_switches_on_rate_limit_and_keeps_task_intact():
    seen, clk = [], Clock()
    sw = ModelSwitcher(POOL, sleep=clk.sleep, clock=clk,
                       make=scripted({"a": [429], "b": [503], "c": [PLAN]}, seen))
    assert sw.plan({"objective": "x", "n": 1}) == PLAN
    assert [m for m, _ in seen] == ["a", "b", "c"]
    assert len({t for _, t in seen}) == 1          # identical task to every model
    assert sw.current == 2 and clk.t == 0           # no waiting, just switching


def test_whole_pool_limited_takes_break_resets_and_continues():
    seen, clk = [], Clock()
    sw = ModelSwitcher(POOL, sleep=clk.sleep, clock=clk,
                       make=scripted({"a": [429, PLAN], "b": [429], "c": [0]}, seen))
    assert sw.plan({"objective": "x"}) == PLAN
    assert clk.t == 180                             # one 3-minute pool break
    assert any(t.get("pool") == "exhausted" for t in sw.trace)


def test_invalid_plan_and_400_also_switch():
    seen, clk = [], Clock()
    sw = ModelSwitcher(POOL, sleep=clk.sleep, clock=clk,
                       make=scripted({"a": ["bad"], "b": [400], "c": [PLAN]}, seen))
    assert sw.plan({"objective": "x"}) == PLAN


def test_auth_failure_is_owner_boundary_not_rotated():
    seen, clk = [], Clock()
    sw = ModelSwitcher(POOL, sleep=clk.sleep, clock=clk,
                       make=scripted({"a": [401], "b": [PLAN], "c": [PLAN]}, seen))
    with pytest.raises(OwnerAuthError):
        sw.plan({"objective": "x"})
    assert [m for m, _ in seen] == ["a"]


def test_rested_model_skipped_until_cooldown_passes():
    seen, clk = [], Clock()
    sw = ModelSwitcher(POOL[:2], sleep=clk.sleep, clock=clk,
                       make=scripted({"a": [429, PLAN], "b": [PLAN, PLAN]}, seen))
    sw.plan({"j": 1})                               # a limited -> b
    sw.current = 0
    sw.plan({"j": 2})                               # a still resting -> b again
    clk.t += 91
    sw.current = 0
    sw.plan({"j": 3})                               # a rested -> a
    assert [m for m, _ in seen] == ["a", "b", "b", "a"]


def test_optional_give_up_limit():
    clk = Clock()
    sw = ModelSwitcher(POOL[:1], sleep=clk.sleep, clock=clk, max_pool_breaks=1,
                       make=scripted({"a": [429, 429]}, []))
    with pytest.raises(ReasonerError, match="pool exhausted"):
        sw.plan({"objective": "x"})


def test_load_pool_from_repo_routes():
    routes = ROOT / "icarus/runtime/approved-routes.json"
    google_only = load_pool(routes, "gk")
    assert google_only[0]["model"] == "gemini-3.5-flash-lite"
    assert all("generativelanguage" in e["base"] for e in google_only)
    both = load_pool(routes, "gk", "ok")
    assert len(both) > len(google_only) and both[-1]["model"].endswith(":free")
    with pytest.raises(ReasonerError):
        load_pool(routes, "")


def test_load_pool_rejects_paid_route(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"routes": [{"provider": "openrouter", "model": "x/paid", "approved": True,
                                         "costPolicy": "verified-zero-cost"}]}))
    with pytest.raises(ReasonerError, match="invalid route"):
        load_pool(p, "gk", "ok")


def test_every_model_gets_the_same_icarus_identity():
    got = []

    class R:
        def __init__(self, e, ident):
            self.m, self.ident = e["model"], ident

        def plan(self, task):
            got.append((self.m, self.ident))
            if self.m == "a":
                raise ReasonerHTTPError(429, "limited")
            return PLAN

    clk = Clock()
    sw = ModelSwitcher(POOL, sleep=clk.sleep, clock=clk, identity=lambda: "I am Icarus",
                       make=lambda e, ident: R(e, ident))
    sw.plan({"objective": "x"})
    assert got == [("a", "I am Icarus"), ("b", "I am Icarus")]


def test_identity_loaded_from_repo_memory_files():
    from icarus.primitives.identity import OPENING, load_identity
    text = load_identity(ROOT)
    assert text.startswith(OPENING)
    assert (ROOT / "icarus/memory/identity.md").read_text(encoding="utf-8").strip()[:40] in text
    assert "RECENT TRAINING" in text and len(text) < 20000


def test_identity_reaches_the_model_request():
    import http.server
    import threading
    seen = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            out = json.dumps({"choices": [{"message": {"content": json.dumps(PLAN)}}]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(out)))
            self.end_headers(); self.wfile.write(out)

        def log_message(self, *a):
            pass

    from icarus.primitives.reasoner import OpenAICompatReasoner
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        OpenAICompatReasoner(f"http://127.0.0.1:{srv.server_port}/v1", "m", identity="I am Icarus").plan({"x": 1})
    finally:
        srv.shutdown()
    system = seen["body"]["messages"][0]["content"]
    assert system.startswith("I am Icarus") and '"commands"' in system
