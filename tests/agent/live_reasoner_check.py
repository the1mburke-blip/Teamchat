"""Manual, workflow_dispatch-only live check for OpenAICompatReasoner (Task #4).

Not part of the pytest suite (test_core.py / test_governed.py stay hermetic,
no network). This script makes one real HTTP call to a free-tier OpenRouter
model using the repo's OPENROUTER_API_KEY Actions secret, proving the
reasoner's HTTP/parse/error-mapping path actually works end to end.

Run only via the "Icarus core: live reasoner check" GitHub Actions workflow
(workflow_dispatch), never automatically and never from a chat session with
exposed credentials.

Model ids are not stable on OpenRouter's free tier; 2026-10-29's attempt used
meta-llama/llama-3.1-8b-instruct:free, which had been removed by 2026-11-03
(confirmed via live HTTP 404 from the reasoner itself, and via the current
openrouter.ai/api/v1/models listing). Two current free models are listed
below in order; OpenAICompatReasoner already fails over on HTTP 404.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from icarus.agent.reasoners import OpenAICompatReasoner, ReasonerUnavailable  # noqa: E402

MARKER = "ICARUS_LIVE_OK"

def main() -> int:
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("BLOCKED: OPENROUTER_API_KEY not present in environment")
        return 2

    endpoints = [
        {
            "base_url": "https://openrouter.ai/api/v1",
            "model": "nvidia/nemotron-3.5-super-vl:free",
            "api_key_env": "OPENROUTER_API_KEY",
        },
        {
            "base_url": "https://openrouter.ai/api/v1",
            "model": "recursive/flint-v1.0:free",
            "api_key_env": "OPENROUTER_API_KEY",
        },
    ]
    reasoner = OpenAICompatReasoner(endpoints, timeout=60)
    prompt = f"Reply with exactly this token and nothing else: {MARKER}"
    try:
        out = reasoner.complete(prompt)
    except ReasonerUnavailable as e:
        print(f"BLOCKED: ReasonerUnavailable: {e}")
        return 1

    print(f"RAW_OUTPUT: {out!r}")
    if MARKER in out:
        print("RESULT: PASS - live HTTP round trip confirmed, marker echoed back")
        return 0
    print("RESULT: PARTIAL - got a live HTTP response but marker not echoed verbatim")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
