# HumanVibe OpenRouter Free Chair Roster

Verified against OpenRouter's live free-model catalog on 2026-09-23.

These are role-equivalent **shadow chairs**, not claims that the underlying models are identical to the premium models. Their job is to absorb safe first-pass execution and learning before premium allowance is consumed.

| HumanVibe shadow | OpenRouter model | Model slug | Primary role |
|---|---|---|---|
| Luna(or) | NVIDIA Nemotron 3 Ultra (free) | `nvidia/nemotron-3-ultra-550b-a55b:free` | coordination, orchestration, deep reasoning, research, multi-step planning |
| Sol(or) | Poolside Laguna S 2.1 (free) | `poolside/laguna-s-2.1:free` | software engineering, coding-agent work, terminal/execution planning |
| Gemini(or) | Google Gemma 4 31B (free) | `google/gemma-4-31b-it:free` | multimodal reasoning, document understanding, tool/function calling, strategy/research |
| DeepSeek(or) | Cohere North Mini Code (free) | `cohere/north-mini-code:free` | technical specialist, agentic coding, terminal work, interleaved reasoning/tool use |
| Claude(or) | NVIDIA Nemotron 3 Super (free) | `nvidia/nemotron-3-super-120b-a12b:free` | independent critique, long-context reasoning, planning, second-pass review |

## Routing

1. Determine which premium chair would normally own the task.
2. If the task is safe for free inference and the shadow has the required capability, route to that chair's `(or)` mirror first.
3. Apply the full job-start gate: history review, Training Matrix quote/relevance, model identity, and allowance estimate.
4. Give the shadow at most 7 educated attempts. Log every failure before another call.
5. On attempt 7 failure, send the complete learning packet to the matching premium chair.
6. Premium attempt 1 must start from the accumulated shadow evidence; it may not restart blind.
7. HUMAN_ELEMENT or hard authentication/capability requirements bypass the free shadow immediately as defined by the operating rules.

## Allowance

OpenRouter Free is a **single shared 50-request/day pool**. Five shadows do not each receive 50 calls.

Default planning allocation:
- 10 calls worth of daily capacity per shadow.
- Maximum 7 calls on one task.
- 3 calls worth of reserve per shadow.
- If all five shadows legitimately use all 7 task attempts: **35 task calls + 15 reserve calls = 50 total**.

The reserve is shared in reality; the per-chair 10-call split is a planning envelope, not an OpenRouter-enforced quota.

## Zero-spend and data boundary

- Revalidate the exact model slug as free before use.
- Never enable automatic paid fallback.
- If a listed free endpoint disappears, mark that shadow unavailable and select a replacement only after verifying the replacement is currently free and role-appropriate.
- Do not send credentials, secrets, private customer data, owner-private data, or other confidential material to free endpoints.
- Use sanitized task packets. Tasks that require protected data or owner authentication bypass the free layer.
