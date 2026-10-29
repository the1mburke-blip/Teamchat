"""Icarus Core: the agent. One loop, one identity. Reasoners and hands run inside this loop, never above it.

perceive -> recall -> decide (reasoner proposes) -> authorize (kernel) -> act (hand) -> verify (kernel) -> write back
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .kernel import Grant
from .memory import MemoryRejected

RULES = (
    "You are the reasoning engine for Icarus. You do not act; Icarus acts. Reply with exactly ONE JSON object.\n"
    '  Call a tool: {"action":"tool","tool":"<name>","args":{...}}\n'
    '  Finish:      {"action":"finish","claim":"<what you did>","evidence":[{"kind":"file_exists|file_sha256|text_contains",'
    '"path":"...","sha256":"...","text":"..."}],"lesson":"<optional, must include an Evidence: <path> line>"}\n'
    "Any verdict you write is ignored. Only Icarus's kernel decides PASS, and only from evidence it checks itself."
)
MAX_INVALID_IN_A_ROW = 2


@dataclass
class Result:
    verdict: str
    reasons: tuple
    steps: int
    task_id: str


def parse_proposal(text):
    """Pull the first JSON object out of model text. Returns dict or None. Never executes anything."""
    i = text.find("{")
    if i < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[i:])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) and obj.get("action") in ("tool", "finish") else None


class IcarusCore:
    def __init__(self, memory, reasoner, kernel, hand):
        self.memory, self.reasoner, self.kernel, self.hand = memory, reasoner, kernel, hand

    def _prompt(self, task, recalled, history):
        tools = "\n".join(f"- {k}: {v}" for k, v in self.hand.tools().items())
        hist = "\n".join(history[-12:]) or "(none)"
        return (
            f"{self.memory.identity_text()}\n\n{RULES}\n\nTOOLS:\n{tools}\n\n"
            f"RECALLED LESSONS:\n{recalled or '(none)'}\n\nTASK:\n{task}\n\nHISTORY:\n{hist}\n"
        )

    def run(self, task, grant, max_steps=10):
        if not isinstance(grant, Grant):
            raise TypeError("a Grant is required; default is deny")
        tid = grant.task_id
        self.memory.identity_text()  # raises IdentityMissing before any model call
        self.kernel.log({"type": "task_start", "task": tid, "task_sha256": hashlib.sha256(task.encode()).hexdigest()})
        recalled = self.memory.recall(task)
        history, invalid, steps = [], 0, 0
        while steps < max_steps:
            steps += 1
            prompt = self._prompt(task, recalled, history)
            out = self.reasoner.complete(prompt)
            self.kernel.log({"type": "reasoner_output", "task": tid, "sha256": hashlib.sha256(out.encode()).hexdigest(), "len": len(out)})
            prop = parse_proposal(out)
            if prop is None:
                invalid += 1
                if invalid >= MAX_INVALID_IN_A_ROW:
                    return self._end(tid, "FAIL", ("reasoner produced invalid output twice",), steps)
                history.append("ICARUS: your last reply was not a valid JSON proposal. Reply with one JSON object per the rules.")
                continue
            invalid = 0
            if prop["action"] == "finish":
                v = self.kernel.adjudicate(tid, prop.get("evidence"))
                if v.verdict == "PASS" and isinstance(prop.get("lesson"), str):
                    try:
                        self.memory.write_back(prop["lesson"])
                        self.kernel.log({"type": "memory_write", "task": tid, "ok": True})
                    except MemoryRejected as e:
                        self.kernel.log({"type": "memory_write", "task": tid, "ok": False, "reason": str(e)})
                return self._end(tid, v.verdict, v.reasons, steps)
            tool, args = prop.get("tool"), prop.get("args", {})
            d = self.kernel.authorize(grant, tool, args)
            if not d.allowed:
                history.append(f"ICARUS: DENIED {tool}: {d.reason}")
                if self.kernel.halted(tid) or d.reason == "budget exhausted":
                    return self._end(tid, "FAIL", (d.reason,), steps)
                continue
            try:
                res = self.hand.execute(tool, args)
            except Exception as e:  # a hand failing is evidence, not a crash
                res = {"ok": False, "error": type(e).__name__}
            self.kernel.log({"type": "tool_result", "task": tid, "tool": tool, "sha256": hashlib.sha256(json.dumps(res, sort_keys=True).encode()).hexdigest()})
            history.append(f"ICARUS: ran {tool}({json.dumps(args)[:200]}) -> {json.dumps(res)[:600]}")
        return self._end(tid, "FAIL", ("step limit reached",), steps)

    def _end(self, tid, verdict, reasons, steps):
        self.kernel.log({"type": "task_end", "task": tid, "verdict": verdict, "reasons": list(reasons), "steps": steps})
        return Result(verdict, tuple(reasons), steps, tid)
