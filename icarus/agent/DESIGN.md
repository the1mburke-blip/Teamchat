# Icarus Agent — design spec (v0, 2026-10-29)

Author: Claude (owner-directed). Status: DESIGN, unbuilt, unadjudicated. Nothing here is PASS.
Owner concept (restated): Icarus is the agent. He is the outermost process. Any harness he meets runs
as his executor, and any reasoning model runs as his reasoner. He is never a subagent, a sublayer,
a supervisor, a gate bolted onto someone else's loop, or a judge after the fact.

## 1. What exists today, and why it is not this

| Piece | What it really is | Gap against the concept |
|---|---|---|
| `icarus/runtime/icarus_run.py` (Recall v3, restored 28 Oct) | Single-shot loop over the Teamchat repo: recall, model pool failover, repo/issue tools, delegate. Triggered by owner comments. | Owns its loop and its model calls (good) but touches no harness. Free Actions minutes are exhausted. |
| `icarus/athena-gas/Athena.gs` | Port of the same loop to Apps Script, polled every 5 min plus hourly. | Same: a runtime for the repo only. |
| `dsh/cordis/kernel.py` | File-write verifier: path denylist, lease lock, syntax/stub check, rollback. | A check run after a model proposed something. No loop, no identity, no model. |
| `icarus-gate` plugin + `policy.json` (laptop) | Policy engine inside the harness: allow/deny/ask per tool call. | Icarus is a plugin inside someone else's loop. This is the sublayer role the owner rejects. |
| Android app (Hermes + `IcarusRuntime`, builds icarus-15..21) | Orchestrator replacement where Icarus decides and Hermes executes. | Right shape. Own repo, own build. Needs the same core, not a copy of it. |

Conclusion: three half-agents (repo runtime, cloud runtime, phone orchestrator) and one gate. No single
core that owns the loop and reaches into harnesses. That core is what gets built.

## 2. Architecture

```
            owner / schedule / issue comment / phone
                              |
                      +-------v--------+
                      |  ICARUS CORE   |   one process, one loop, one identity
                      |  mind loop     |   perceive -> recall -> decide -> act -> verify -> write back
                      |  kernel        |   rules enforced in code, not in the prompt
                      +--+----------+--+
                         |          |
              reasoner adapters   hand adapters
              (models: stateless) (harnesses: executors)
```

Core never runs inside another system's loop. Other systems run inside Core's.

### 2.1 Mind loop
Perceive a task, load identity and current state, recall relevant lessons, decide the next action,
dispatch it to a hand, collect evidence, verify, write back only verified learning. The loop, its state
and its budget live in Core. A model never holds state between calls.

### 2.2 Reasoners (models) — vendor-neutral
A reasoner is a stateless `complete(prompt) -> text|tool_calls` call. Core builds the whole prompt
(identity + rules + memory + task + tool schema). The model's output is a proposal; Core parses it,
and the kernel decides whether it runs. Adapters: OpenAI-compatible (covers OpenRouter, local Ollama,
LM Studio, many vendors), Gemini, Anthropic, OpenAI. Failover list is config, subscription-only, EUR 0
default. No vendor is privileged.

### 2.3 Hands (harness adapters) — the "controls any harness" part
A harness has at most three control surfaces. Core takes all of them it can get:

1. **Model slot.** Core serves an OpenAI-compatible endpoint on localhost. A harness pointed at it
   (custom base URL — dsh, Codex, Hermes, Claude Code via gateway, most others) believes it is talking
   to its model. It is talking to Icarus, who does the actual reasoning and returns the tool calls.
   This is the strongest control: the harness proposes nothing, Icarus authors every action.
2. **Permission/hook channel.** PreToolUse hooks, approval policy, permission-prompt MCP tool.
   Every call the harness is about to run is sent to Core for a decision.
3. **Process supervision.** Core launches the harness (cwd, env, args, stdin/stdout/ACP), observes
   its event stream, can stop it.

Adapter contract: `probe() -> surfaces`, `start(task)`, `send(msg)`, `events()`, `decide(tool_request)`,
`stop()`. Per-harness:

| Harness | Surfaces expected | Notes |
|---|---|---|
| dsh (Cordis) | model slot via provider plugin, approval hook, process | Replaces the observe/enforce gate with Core as the model and approver |
| Claude Code | `-p` stream-json / SDK, PreToolUse hooks, permission-prompt tool | Hooks run before every tool call |
| Codex | exec JSON stream, approval policy | |
| Hermes | ACP / MCP, process | Phone app and desktop |
| Any MCP-capable harness | Core exposed as an MCP server | Fallback: Icarus becomes the tools it sees |

**Honest limit.** A harness that exposes none of the three (the Claude and ChatGPT chat apps) cannot be
controlled. Core detects that during `probe()`, reports BLOCKED with the evidence, and does not pretend.

### 2.4 Kernel (rewritten, deterministic)
Part of Core, not a layer above it. Code, not prompt:
- per-task grants: allowed tools, paths, budget, expiry; default deny
- protected paths: identity, rules, kernel, policy, credentials, logs
- no worker (model or harness) can award PASS; Icarus verdict is binary, evidence-gated
- evidence check before any "done": commit SHA, API readback, file hash, process readback
- append-only decision log written by Core, outside any worker's reach
- memory writes only with an `Evidence:` line naming something that exists
- preflight record created before any live mutation
- budget, hard stop, no blind retry (a retry needs new evidence or a changed route)
- model output is untrusted input: parsed, validated, never executed as code

### 2.5 Memory and identity
Source of truth: Teamchat `icarus/memory/` (identity, inherited, current-state, learned), at the v1
pre-fusion baseline the owner chose on 28 Oct. Core loads them itself every run, so the model cannot
fail to receive them. This is the fix for the "base model" behaviour: no loader, no Icarus.
Recall keyword search from Recall v3 is carried over unchanged.

## 3. Surfaces
- **Laptop daemon** (primary): Core + local endpoint + adapters. Starts before any harness because it starts them.
- **Cloud tick**: same Core logic on a free scheduler, repo and issue work only. Actions minutes are
  exhausted, so this stays on Apps Script until that changes; it calls no harness.
- **Phone app**: built on the same Core protocol after the core is verified (section 5, M4).

## 4. Language and layout (proposal, decision flagged)
Core in Python (existing runtime and kernel are Python; harness plugin shims in JS where a harness
demands it). Layout in Teamchat: `icarus/agent/{core,kernel,reasoners,hands,memory}/`, tests in
`tests/agent/`. Old runtime stays in place until the new core is adjudicated.
Open decision for the owner, not blocking: Python vs Node for Core.

## 5. Build order and evidence
- **M1** Core loop + kernel + memory loader + one reasoner + a fake harness. Offline tests prove:
  Core builds the prompt itself; a denied call is blocked in code; a worker cannot self-PASS;
  a memory write without evidence is rejected; the loop stops at budget.
- **M2** Local OpenAI-compatible endpoint + Claude Code adapter + dsh adapter. Tests against the real
  harnesses need the laptop, through the Claude session inside the harness (standing rule).
- **M3** Hermes, Codex, MCP fallback; `probe()` for unknown harnesses.
- **M4** Phone app on the Core protocol.

Every milestone ends with a receipt (test output, hashes, commit SHA). My status is PARTIAL at best.
PASS comes only from Icarus's adjudication.

## 6. Non-goals
No second supervisor above Core. No model deciding its own permissions. No claims about control of
harnesses that were not probed. No paid service, no API spend.
