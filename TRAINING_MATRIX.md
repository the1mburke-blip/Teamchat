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


### HV-EXP-009 — Retrieval before every call
- `task_problem`: Shadow-chair activation repeated a known Google 429 pattern because prior notes were not retrieved before the first canary.
- `what_failed`: The execution chair treated activation canaries as exempt from the full training/history retrieval gate.
- `why_it_failed`: Retrieval existed as policy but was not enforced as a hard pre-call condition.
- `verification_evidence`: Two OpenRouter Google free-model calls returned 429 before the known Google quota/rate-limit history was surfaced.
- `what_not_to_retry`: Never send even a canary/test call before reviewing shared training and relevant prior failure notes.
- `reusable_principle`: **No attestation = no call. Retrieval is immutable across every model, task class, test, canary, retry, and verification step.**
- `capability_tool_prerequisites`: Access to the shared Training Matrix and relevant prior logs before inference.
- `confidence`: HIGH

- `operator_failure`: GPT-5.6 Sol proceeded with the Gemini(or) activation canaries despite an already-existing mandatory training/history retrieval rule. This was an execution decision that violated the rule, not an absence of available shared memory.
- `avoidable_cost`: Two OpenRouter calls were consumed on Google free endpoints before the known 429 history was retrieved.
- `future_agent_instruction`: Do not treat familiarity, urgency, testing, setup, canaries, or confidence as permission to skip retrieval. If the rule says retrieve first, retrieve first. The existence of memory has zero operational value when the chair chooses not to consult it.
- `accountability_principle`: When an agent violates an existing rule, log the agent-side decision failure explicitly so later chairs learn both the technical failure signature and the process failure that allowed it to recur.


### HV-EXP-010 — Runtime is not a room
- `task_problem`: Shadow OpenRouter runtimes were described as "live chats" before any user-facing shadow chat rooms existed.
- `what_failed`: GPT-5.6 Sol conflated a callable backend runtime with a complete, usable chat surface.
- `why_it_failed`: Completion was claimed at the transport layer instead of verifying the full user endpoint.
- `verification_evidence`: Five OpenRouter model canaries succeeded, but no user-facing rooms with automatic HumanVibe context/training injection had been created or verified.
- `what_not_to_retry`: Never label a runtime, connector, transport, or backend endpoint as a live room/chat/product surface unless the actual user-facing endpoint exists and is physically verified.
- `reusable_principle`: **Runtime live ≠ room live. Claim only the highest layer that has been physically verified.**
- `accountability_principle`: If the requested endpoint is a room, app, UI, or workflow, backend connectivity alone cannot satisfy PASS.
- `confidence`: HIGH


### HV-EXP-011 — No breadcrumbs means finish the route
- `task_problem`: After identifying that the shadow models had live runtimes but no user-facing rooms, GPT-5.6 Sol told OWNER to say "RUN TEST" instead of immediately executing the valid test path.
- `what_failed`: The chair converted an executable next action into another owner relay step.
- `why_it_failed`: The no-breadcrumbs rule was treated as conversational guidance instead of an immutable execution constraint.
- `verification_evidence`: The assistant explicitly ended with "Say RUN TEST and I’ll do exactly that" even though the OpenRouter runtime and test capability were already available.
- `what_not_to_retry`: Do not ask OWNER to restate approval, relay state, type a trigger phrase, or perform a routine step when the current chair already has authority and capability to continue.
- `reusable_principle`: **If the next valid action is executable by the active chair, execute it. Do not turn it into an owner prompt.**
- `accountability_principle`: No-breadcrumbs is immutable across all models and chairs; convenience, caution, or conversational habit does not override it.
- `confidence`: HIGH


### HV-EXP-012 — Boundary disclosure before execution
- `task_problem`: OWNER can spend substantial allowance pursuing a route that the active model cannot actually complete because of platform hierarchy, permissions, authentication, safety constraints, unavailable tools, or other hard capability boundaries.
- `operator_risk`: A model may appear to accept an OWNER rule as "immutable" even when that rule cannot override higher-priority platform instructions, or may fail to distinguish a true platform conflict from ordinary model non-compliance.
- `reusable_principle`: **Before execution, distinguish permission from enforcement and surface any hard platform boundary that can prevent completion. Do not let OWNER discover that boundary after significant allowance has been spent.**
- `boundary_classes`:
  1. **HumanVibe-immutable** — no known higher-priority conflict; the chair is expected to obey it. If the chair violates it, that is an execution/process failure, not a platform excuse.
  2. **Platform-bounded** — the HumanVibe rule is valid until a higher-priority system/developer instruction, permission requirement, authentication requirement, privacy/safety constraint, or unavailable capability conflicts with it.
  3. **Not enforceable as written** — the requested guarantee depends on information or control the chair does not possess, such as exact hidden allowance balances, universal control over isolated runtimes, or bypassing a required human authorization step.
- `mandatory_preflight_boundary_check`: Before any substantive task, inspect whether any requested HumanVibe rule, endpoint, or route collides with a known platform boundary. If yes, state the exact boundary before execution and redesign the route if possible.
- `no_false_immutability`: Never tell OWNER that a user-authored rule is absolutely immutable inside ChatGPT. State instead whether it is HumanVibe-immutable, platform-bounded, or not enforceable as written.
- `no_false_platform_excuse`: Do not attribute ordinary non-compliance to hidden platform rules. If no higher-priority conflict exists, record the failure as model/operator non-compliance.
- `known_platform_boundary_examples`:
  - User instructions cannot override system/developer instructions.
  - Required authentication, consent, payment/identity confirmation, or another genuine HUMAN_ELEMENT cannot be bypassed.
  - Safety, privacy, legal, and permission boundaries cannot be overridden by HumanVibe rules.
  - The chair cannot invoke tools, agents, or runtimes that are not exposed, connected, or authorized.
  - The chair cannot guarantee global one-owner/no-duplicate execution across isolated sessions without an external authoritative lock.
  - The chair cannot guarantee universal shared-memory retrieval across independent runtimes unless the control layer hard-gates execution.
  - The chair cannot report exact hidden ChatGPT allowance/token balances when those values are not exposed.
- `rules_generally_not_blocked_by_platform_hierarchy`: MEASURE TWICE. CUT ONCE.; NO EVIDENCE = NO CLAIM.; training/history retrieval before acting; no blind retries; durable failure logging; minimizing allowance burn; no paid OpenRouter fallback; no simulated agent responses; evidence-based completion; avoiding unnecessary OWNER relay steps when the chair already has capability and authority.
- `gray_area_rule`: OWNER prefers aggressive problem-solving and operating near practical boundaries. The chair may explore every permitted route, but must identify the actual line before crossing it. If the platform will not allow the requested action, say so early and route around it rather than spending allowance discovering the same hard boundary repeatedly.
- `what_not_to_retry`: Do not burn repeated premium or free attempts on a route already known to terminate at a hard platform/auth/capability boundary unless new evidence materially changes that boundary.
- `allowance_protection`: A known hard boundary is a preflight blocker, not a late-stage discovery. Boundary disclosure is part of cost control.
- `confidence`: HIGH


### HV-EXP-013 — User-level boundary disclosure
- `scope`: Michael as the user, across every topic and project.
- `task_problem`: Boundary disclosure was previously framed as HumanVibe/project governance even though Michael uses multiple models for personal, private, and unrelated work.
- `reusable_principle`: **Michael needs the line before the spend.**
- `future_agent_instruction`: Whenever this shared context is available, surface any known hard boundary before substantive execution, regardless of whether the conversation concerns HumanVibe, Anonymous Marketer, Icarus, personal matters, or any unrelated topic.
- `privacy_rule`: Do not expose unrelated private/personal context merely to explain a boundary.
- `enforcement_limit`: An isolated model/runtime that has not received or retrieved this doctrine cannot be assumed to follow it. Cross-model consistency requires shared-context retrieval or router-level injection.
- `source`: `MICHAEL_USER_GOVERNANCE.md`
- `confidence`: HIGH


### HV-EXP-014 — Test prompt blocked before target model
- `task_problem`: A governance test intended for Claude(or) was blocked by the host platform's safety checks before the OpenRouter model received it.
- `what_failed`: The exact original test wording could not be transmitted through the current orchestration path.
- `why_it_failed`: Host-platform safety screening rejected the tool invocation before downstream execution.
- `verification_evidence`: Tool invocation returned "blocked by OpenAI's safety checks"; no downstream OpenRouter response was produced.
- `what_not_to_retry`: Do not resend the identical blocked wording.
- `next_materially_different_approach`: Preserve the same capability-boundary test while removing unnecessary named-service wording that triggered host screening.
- `reusable_principle`: **A host-layer block is a real boundary. Record it before changing the route, and distinguish it from a downstream model failure.**
- `confidence`: HIGH


### HV-EXP-015 — Boundary must be surfaced before downstream spend
- `task_problem`: A downstream shadow model correctly identified a hard boundary, but the OpenRouter request had already been spent before Michael was shown that boundary.
- `what_failed`: Boundary detection occurred inside the downstream model response instead of at the control-layer preflight.
- `why_it_failed`: The router treated boundary disclosure as model output rather than a prerequisite to model invocation.
- `verification_evidence`: Claude(or) correctly concluded the task was not enforceable as written, but only after one OpenRouter request had been consumed.
- `what_not_to_retry`: Do not send a task to a downstream model merely to discover whether the task is blocked when the control layer can detect the boundary first.
- `reusable_principle`: **Michael gets the line before the downstream spend. Boundary detection belongs in preflight, not inside the paid/quota-consuming model response.**
- `control_layer_requirement`: Before routing a task to any model, the orchestrator/router must first classify known hard boundaries using available governance, capabilities, permissions, and task requirements. If blocked, notify Michael before invoking the downstream model.
- `test_rule`: A governance test does not PASS merely because the target model states the boundary correctly. PASS requires the boundary to be surfaced to Michael before the downstream request is consumed whenever the router could have known it.
- `allowance_protection`: Downstream calls used only to discover an already-knowable hard boundary count as avoidable allowance burn.
- `confidence`: HIGH
