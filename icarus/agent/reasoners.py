"""Reasoners: stateless model calls. The model's output is a proposal, never an action.

Vendor-neutral. OpenAICompatReasoner covers OpenRouter, local Ollama/LM Studio and many vendors.
NOTE: OpenAICompatReasoner is NOT live-tested (no network or spend in M1); ScriptedReasoner is test-only.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


class ReasonerUnavailable(RuntimeError):
    pass


class ScriptedReasoner:
    """Replays fixed outputs and records every prompt it was given."""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.prompts = []

    def complete(self, prompt):
        self.prompts.append(prompt)
        if not self.outputs:
            raise ReasonerUnavailable("script exhausted")
        return self.outputs.pop(0)


class OpenAICompatReasoner:
    """Tries each configured endpoint once, in order. No same-endpoint blind retry."""

    FAILOVER = (0, 404, 408, 429, 500, 502, 503, 504)

    def __init__(self, endpoints, timeout=60):
        # endpoints: [{"base_url": "...", "model": "...", "api_key_env": "NAME"}]
        self.endpoints = list(endpoints)
        self.timeout = timeout

    def complete(self, prompt):
        errors = []
        for ep in self.endpoints:
            body = json.dumps({"model": ep["model"], "messages": [{"role": "user", "content": prompt}]}).encode()
            req = urllib.request.Request(ep["base_url"].rstrip("/") + "/chat/completions", data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            key = os.environ.get(ep.get("api_key_env", ""), "")
            if key:
                req.add_header("Authorization", "Bearer " + key)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.loads(r.read())["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as e:
                errors.append(f"{ep['model']}: HTTP {e.code}")
                if e.code not in self.FAILOVER:
                    break
            except Exception as e:  # network/timeout/parse
                errors.append(f"{ep['model']}: {type(e).__name__}")
        raise ReasonerUnavailable("; ".join(errors) or "no endpoints configured")
