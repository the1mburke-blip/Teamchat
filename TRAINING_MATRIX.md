# HumanVibe Shared Training Matrix

## Purpose

This is the durable, model-independent experience pool for HumanVibe agents.

A chair does not need built-in memory to benefit from team learning. Before execution of any executable task, the current chair retrieves the relevant entries here plus relevant issue/log history. Verified lessons discovered by one chair become reusable training for every later chair.

**Knowledge belongs to HumanVibe, not to the model occupying the chair.**

## Mandatory retrieval gate

Before the first execution attempt on every executable task:

1. Read the relevant task/Issue and current coordination state.
2. Search this matrix for matching task, system, tool, failure signature, or capability.
3. Review the executing chair's own relevant prior logs when available.
4. Review relevant prior-team attempts.
5. Carry forward verified `what_not_to_retry`, prerequisites, recoveries, and evidence.
6. Record `TRAINING_REVIEW: PASS` before entering EXECUTING.
7. Quote one verbatim line from this matrix that is materially relevant to the task; record its lesson ID/section heading and one sentence explaining the relevance.
8. Record the exact model/runtime occupying the chair and an estimated token/request/allowance cost before execution.

If no relevant entry exists, record `NONE FOUND`; do not invent prior knowledge. When no prior task-specific lesson exists, quote the most relevant governing seed lesson or principle instead.

## Mandatory job-start proof

No executable task enters EXECUTING without all of:

- `MODEL_CHAIR`
- `HISTORY_REVIEW: PASS`
- `TRAINING_REVIEW: PASS`
- `TRAINING_QUOTE` — exact text from this file
- `TRAINING_SOURCE` — lesson ID or section heading
- `TRAINING_RELEVANCE` — why that quote changes or constrains this execution
- `ALLOWANCE_ESTIMATE` — tokens, requests, or allowance percentage using the best measurable unit

The quote is proof of retrieval, not decoration. It must be relevant to the actual task. A generic quote selected merely to satisfy the field fails the gate.

At terminal status record `ALLOWANCE_USED` as measured usage when available, otherwise as an explicitly labelled estimate. If expected usage materially changes during execution, stop and re-preflight.

## Failure-to-learning gate

A failed attempt is not disposable.

Before another attempt, durably capture:
- `experience_id`
- `date_utc`
- `source_agent`
- `task_problem`
- `environment_context`
- `symptoms_failure_signature`
- `attempts_made`
- `what_failed`
- `why_it_failed`
- `successful_recovery` or `NONE`
- `verification_evidence`
- `what_not_to_retry`
- `reusable_principle`
- `capability_tool_prerequisites`
- `confidence`
- `superseded_by` or `NONE`

The next attempt must change the approach or be justified by new evidence. Repeating the same failed action without material change is prohibited.

## Success-to-learning gate

A successful recovery should also be captured when it teaches a reusable route, prerequisite, failure avoidance, or verification method.

Do not record routine noise. Record only evidence-backed knowledge likely to improve a future execution decision.

## Precedence

1. Hard safety, permission, cost, and owner rules.
2. Current task scope and current verified system state.
3. Relevant verified entries in this training matrix.
4. Relevant agent/team execution logs.
5. Native model memory.
6. General model knowledge.

Older entries remain historical evidence but may be superseded by newer verified entries.

## Retry budget principle

A bounded free-attempt budget may be used only as a learning loop:

`ATTEMPT → CAPTURE FAILURE → LEARN → CHANGE APPROACH → RETRY`

If an attempt produces no new evidence and no materially different route, stop rather than consume another attempt. Escalate to a stronger/premium chair only when the free learning lane cannot progress or the required capability is unavailable.

## Seed lessons

### HV-EXP-001 — Capability before chair
A strong model without the required read/write/verification capability is the wrong execution chair. Capability-gate the entire route before spending execution attempts.

### HV-EXP-002 — No blind execution
A chair must review relevant prior attempts before acting. Starting from the prompt alone when previous failure evidence exists wastes time, tokens, and repeats known mistakes.

### HV-EXP-003 — Failure must become shared training
A failure only improves the system when its signature, cause, evidence, do-not-retry condition, and next changed approach are recorded durably and made available to later chairs.

### HV-EXP-004 — Memory is optional; retrieval is mandatory
Native model memory may help, but HumanVibe continuity must not depend on it. Shared durable retrieval is the canonical learning mechanism.

### HV-EXP-005 — Evidence closes the loop
Agent narrative is not completion evidence. A recovery or PASS becomes reusable training only when the final state is physically/readback verified.


## Free-shadow escalation ladder

OpenRouter Free is the first inference layer for eligible work. The premium chairs remain the escalation layer.

- The shared OpenRouter Free account limit is 50 requests/day.
- HumanVibe maintains five role-matched free shadows defined in `FREE_CHAIRS.md`.
- Each shadow receives at most 7 educated attempts on the same task.
- Each failed attempt must be captured before the next, and the next attempt must materially change based on accumulated evidence.
- A nominal 10-call allocation per shadow therefore protects 3 calls for unrelated work, verification, or emergency recovery.
- Across five shadows, 5 × 7 = 35 maximum task attempts if all five roles are legitimately engaged; 15 shared calls remain protected reserve.
- After attempt 7, escalation is vertical to the matching premium counterpart, not an arbitrary lateral model.
- The premium counterpart must read the shadow's complete failure packet plus this Training Matrix before premium attempt 1.
- Premium chairs use the same history/training/failure-capture discipline and a maximum 7-attempt learning cycle before their normal higher-chair/OWNER escalation.
- Any HUMAN_ELEMENT requirement bypasses the model ladder and goes directly to OWNER.
- A hard capability/authentication blocker escalates immediately instead of consuming seven calls.
- Never permit a free-model failure to trigger an automatic paid OpenRouter fallback.
- Revalidate the selected OpenRouter model as a live free endpoint before execution because the free catalog can change.

### HV-EXP-006 — Free intelligence before premium allowance
When a safe, capable free shadow exists, use it to learn first. Premium reasoning should receive the accumulated evidence rather than rediscovering failures from scratch.

### HV-EXP-007 — Reserve is operational capacity
A daily request ceiling is shared infrastructure, not a target to exhaust. Protect reserve calls for verification, emergencies, and unrelated work.


### HV-EXP-008 — Gemini(or) upstream free-pool rate limit
- `experience_id`: HV-EXP-008
- `date_utc`: 2026-09-23T21:54:15.000Z
- `source_agent`: LUNA
- `task_problem`: Activate Gemini(or) shadow chair through OpenRouter Free.
- `environment_context`: OpenRouter authenticated; model `google/gemma-4-31b-it:free`; zero-cost canary.
- `symptoms_failure_signature`: HTTP 429 from Google AI Studio shared upstream pool.
- `attempts_made`: 1
- `what_failed`: Gemma 4 31B free canary was not served.
- `why_it_failed`: OpenRouter reported the upstream provider shared free pool was temporarily rate-limited.
- `successful_recovery`: NONE YET
- `verification_evidence`: OpenRouter error metadata identified `limit_source=upstream_provider_shared_pool`.
- `what_not_to_retry`: Do not immediately repeat the identical Gemma 4 31B request.
- `reusable_principle`: A free endpoint can be valid yet temporarily unavailable; switch to another verified-free role-appropriate endpoint rather than blind retry or paid fallback.
- `capability_tool_prerequisites`: Authenticated OpenRouter connection and verified-free replacement model.
- `confidence`: HIGH
- `superseded_by`: NONE


#### HV-EXP-008 update — attempt 2
- `attempts_made`: 2
- `what_failed`: Replacement `google/gemma-4-26b-a4b-it:free` also returned HTTP 429.
- `why_it_failed`: Same Google AI Studio shared upstream free-pool limit.
- `what_not_to_retry`: Do not spend another activation call on the Google free pool while the provider-level 429 persists.
- `next_materially_different_approach`: Move Gemini(or) to a non-Google verified-free multimodal/tool-capable model.


#### HV-EXP-008 recovery
- `successful_recovery`: Gemini(or) moved to `dots-studio/dots-3-note-preview:free`, a non-Google verified-free multimodal/tool-capable route.
- `verification_evidence`: Successful OpenRouter generation `gen-1790200565-O5YxX2wJWhU5ox8Lmlx8`; provider AtlasCloud; reported generation cost $0.
- `what_not_to_retry`: Do not immediately return Gemini(or) to the Google free shared pool while the provider-level 429 condition persists.
- `superseded_by`: Gemini(or) live mapping in `FREE_CHAIRS.md`.
