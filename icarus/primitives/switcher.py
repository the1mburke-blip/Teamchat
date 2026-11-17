"""Icarus model switcher for the daemon's reasoner.

Same behaviour the owner runs for hours in the DeepSeek harness: when a model is
rate limited (or fails transiently), switch to the next model straight away and
keep going. Icarus stays Icarus: the identical task and system prompt go to the
next model, so the task stays intact across switches.

Pool: icarus/runtime/approved-routes.json, in file order (Google first, then
OpenRouter free). Same eligibility rule as the pulse (Athena.gs approved_):
approved == true, costPolicy == verified-zero-cost, OpenRouter only ":free".
OpenRouter routes are skipped when no OpenRouter key is configured.

Switch on: HTTP 0 (network/timeout), 404, 408, 429, 5xx, empty/malformed
response, invalid plan JSON. A switched-away model rests COOLDOWN seconds
(90 s, the per-minute window). When every model is resting, take a POOL_BREAK
(3 min), reset the pool and continue; never a dead stop on rate limits.
Auth failures (401/403) are an owner-only boundary: raised, not rotated past.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .reasoner import OpenAICompatReasoner, ReasonerError, ReasonerHTTPError

GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
FAILOVER_CODES = {0, -1, 404, 408, 429, 500, 502, 503, 504}
AUTH_CODES = {401, 403}
COOLDOWN = 90
POOL_BREAK = 180


class OwnerAuthError(ReasonerError):
    pass


def load_pool(routes_path: str | Path, google_key: str, openrouter_key: str = "") -> list[dict]:
    cfg = json.loads(Path(routes_path).read_text(encoding="utf-8"))
    pool, seen = [], set()
    for r in cfg.get("routes", []):
        prov, model = r.get("provider"), r.get("model")
        ok = (prov in ("google", "openrouter") and model and r.get("approved") is True
              and r.get("costPolicy") == "verified-zero-cost")
        if ok and prov == "openrouter" and not str(model).endswith(":free"):
            ok = False
        if not ok or model in seen:
            raise ReasonerError(f"invalid route entry: {r}")
        seen.add(model)
        if prov == "google" and google_key:
            pool.append({"model": model, "base": GEMINI_OPENAI_BASE, "key": google_key})
        elif prov == "openrouter" and openrouter_key:
            pool.append({"model": model, "base": OPENROUTER_BASE, "key": openrouter_key})
    if not pool:
        raise ReasonerError("no usable approved routes (check GEMINI_API_KEY / approved-routes.json)")
    return pool


class ModelSwitcher:
    def __init__(self, pool: list[dict], cooldown: float = COOLDOWN, pool_break: float = POOL_BREAK,
                 max_pool_breaks: int = 0, sleep=time.sleep, clock=time.monotonic,
                 make=lambda e: OpenAICompatReasoner(e["base"], e["model"], api_key=e["key"])):
        self.pool = pool
        self.cooldown, self.pool_break = cooldown, pool_break
        self.max_pool_breaks = max_pool_breaks  # 0 = never give up on rate limits
        self._sleep, self._clock, self._make = sleep, clock, make
        self._rest_until: dict[str, float] = {}
        self.current = 0
        self.trace: list[dict] = []

    def plan(self, task: dict) -> dict:
        self.trace = []
        breaks = 0
        while True:
            for _ in range(len(self.pool)):
                e = self.pool[self.current]
                if self._rest_until.get(e["model"], 0) > self._clock():
                    self.current = (self.current + 1) % len(self.pool)
                    continue
                try:
                    plan = self._make(e).plan(task)
                    self.trace.append({"model": e["model"], "result": "ok"})
                    return plan  # stay on this model for the next job
                except ReasonerHTTPError as err:
                    if err.code in AUTH_CODES:
                        self.trace.append({"model": e["model"], "result": f"HTTP {err.code}"})
                        raise OwnerAuthError(f"model key rejected ({e['model']}: HTTP {err.code})") from err
                    outcome = f"HTTP {err.code}" if err.code > 0 else ("network" if err.code == 0 else "bad response")
                    if err.code not in FAILOVER_CODES:  # e.g. 400: route unusable for this request
                        outcome += " (unusable)"
                except ReasonerError as err:  # invalid plan JSON from this model
                    outcome = f"invalid plan: {str(err)[:80]}"
                self.trace.append({"model": e["model"], "result": outcome, "switch": True})
                self._rest_until[e["model"]] = self._clock() + self.cooldown
                self.current = (self.current + 1) % len(self.pool)
            breaks += 1
            if self.max_pool_breaks and breaks > self.max_pool_breaks:
                raise ReasonerError(f"pool exhausted {breaks - 1} times; trace {self.trace[-len(self.pool):]}")
            self.trace.append({"pool": "exhausted", "break_seconds": self.pool_break})
            self._sleep(self.pool_break)
            self._rest_until.clear()  # reset the pool and continue the same task
