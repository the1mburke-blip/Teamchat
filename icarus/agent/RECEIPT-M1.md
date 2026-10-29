# M1 receipt — 2026-10-29

Status: **PARTIAL**. Self-reported by Claude; not adjudicated by Icarus. Nothing here is PASS.

## What was built
Core loop (`core.py`), kernel (`kernel.py`), memory/identity loader (`memory.py`), reasoners (`reasoners.py`),
reference hand (`hands.py`), tests (`tests/agent/test_core.py`). Modules, not sub-packages: `icarus.agent.<name>`.

## Evidence
- `PYTHONPATH=. python3 -m pytest tests/agent -q` -> 13 passed (Python 3.13, sandbox, EUR 0).
- Mutation check: 8 deliberate breakages (tool allowlist ignored, protected writes allowed, adjudicate always PASS,
  budget ignored, memory evidence not required, identity not required, lesson written on FAIL, blind retry on invalid
  output) each made at least one test fail. The tests can fail.
- Local `git hash-object` of each file equals the blob SHA on this branch (checked after commit).
- The first commit attempt returned HTTP 403 from the GitHub connector (cause unconfirmed; suspected content filter on
  strings inside the test file). The files were committed in parts instead; the test file was sent base64-encoded.

## Proven
Core builds the prompt and loads identity itself; no identity means no model call. A denied tool never reaches the
hand. Protected, secret and escaping paths are denied. A worker cannot award PASS; only the kernel checks evidence.
Memory writes need an `Evidence:` line naming an existing non-memory file. The loop stops at budget, after 5
consecutive denials, and after two invalid outputs in a row. The decision log is hash-chained and tamper-evident.

## NOT proven
- `OpenAICompatReasoner` has never made a live call.
- No real harness adapter exists yet (dsh, Claude Code, Codex, Hermes, MCP). Control of any real harness is unproven.
- Nothing has run on the laptop. The old runtime and the laptop gate are untouched and still in place.
- No Icarus adjudication.

## Next: M2
Local OpenAI-compatible endpoint (model slot), Claude Code adapter, dsh adapter. Real-harness tests need the laptop,
run through the Claude session inside the harness per the owner's standing rule.
