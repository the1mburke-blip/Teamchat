"""Primitive 3 - Decoupled Reasoning Engine.

The model only plans. It returns JSON; it never executes anything.
Any OpenAI-compatible /chat/completions endpoint works (local Ollama,
llama.cpp server, vLLM, or a hosted provider) - swap by env vars:

    ICARUS_REASONER_URL    e.g. http://localhost:11434/v1
    ICARUS_REASONER_MODEL  e.g. llama3.1
    ICARUS_REASONER_KEY    optional API key; read from env only,
                           never written to the ledger or run log

Plan contract (what the model must return):
    {"commands": [["argv0", "arg1", ...], ...],
     "files":    [{"path": "relative/path", "content": "..."}, ...],
     "notes":    "optional free text"}
"""
from __future__ import annotations

import json
import os
import urllib.request

SYSTEM_PROMPT = (
    "You plan one job. Reply with a single JSON object only, keys: "
    '"commands" (list of argv lists, no shell), "files" (list of '
    '{"path","content"} with relative paths), "notes" (string). No prose.'
)


class ReasonerError(Exception):
    pass


def parse_plan(text: str) -> dict:
    try:
        plan = json.loads(text)
    except (TypeError, json.JSONDecodeError) as e:
        raise ReasonerError(f"reasoner returned invalid JSON: {e}") from e
    if not isinstance(plan, dict):
        raise ReasonerError("plan must be a JSON object")
    plan.setdefault("commands", [])
    plan.setdefault("files", [])
    if not isinstance(plan["commands"], list) or not all(
        isinstance(c, list) and c and all(isinstance(a, str) for a in c)
        for c in plan["commands"]
    ):
        raise ReasonerError("commands must be a list of non-empty argv string lists")
    if not isinstance(plan["files"], list) or not all(
        isinstance(f, dict) and isinstance(f.get("path"), str)
        and isinstance(f.get("content"), str) for f in plan["files"]
    ):
        raise ReasonerError("files must be a list of {path, content} strings")
    return plan


class FakeReasoner:
    """Scripted reasoner for tests and dry runs. Zero cost."""

    def __init__(self, replies: list[str]):
        self.replies = list(replies)
        self.calls: list[dict] = []

    def plan(self, task: dict) -> dict:
        self.calls.append(task)
        if not self.replies:
            raise ReasonerError("script exhausted")
        return parse_plan(self.replies.pop(0))


class OpenAICompatReasoner:
    def __init__(self, base_url: str | None = None, model: str | None = None,
                 api_key: str | None = None, timeout: int = 120):
        self.base_url = (base_url or os.environ.get("ICARUS_REASONER_URL", "")).rstrip("/")
        self.model = model or os.environ.get("ICARUS_REASONER_MODEL", "")
        self.api_key = api_key if api_key is not None else os.environ.get("ICARUS_REASONER_KEY", "")
        self.timeout = timeout
        if not self.base_url or not self.model:
            raise ReasonerError("ICARUS_REASONER_URL and ICARUS_REASONER_MODEL must be set")

    def plan(self, task: dict) -> dict:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(task)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode(), headers=headers, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                body = json.loads(r.read())
            text = body["choices"][0]["message"]["content"]
        except ReasonerError:
            raise
        except Exception as e:  # network, HTTP, shape
            raise ReasonerError(f"reasoner call failed: {type(e).__name__}: {e}") from e
        return parse_plan(text)
