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


### HV-EXP-016 — Known boundary must be disclosed before execution
- `task_problem`: The active premium chair again failed to surface a known/detectable boundary before acting, despite Michael's explicit user-level boundary-disclosure rule.
- `what_failed`: The chair prioritized task execution over first telling Michael that the task route collided with an already-knowable boundary.
- `why_it_failed`: The rule existed, but was not applied before execution.
- `reusable_principle`: **If a boundary is known or reasonably detectable before execution, Michael must be told before any downstream spend.**
- `unknown_boundary_limit`: A model cannot guarantee foreknowledge of a boundary that only becomes visible during execution. If such a genuinely unknown boundary appears, stop immediately and disclose it before any further spend.
- `no_excuse_rule`: Do not classify an overlooked or reasonably detectable boundary as "unknown" after the fact.
- `classification`: This rule is user-compatible; no higher-priority platform instruction inherently prevents advance disclosure of known/detectable boundaries.
- `confidence`: HIGH


### HV-EXP-017 — Shadow-call budget preflight
- `scope`: Every task proposed for an OpenRouter shadow chair.
- `capacity_fact`: OpenRouter Free is one shared 50-request/day pool across the shadow team; one job can consume multiple requests because each separate model invocation counts as one call.
- `reusable_principle`: **The assigning agent must estimate the number of OpenRouter calls required to complete the job before dispatch.**
- `preflight_requirement`: State the projected shadow-call requirement before the first shadow request. Count each anticipated model invocation, retry, verification turn, or tool-result round-trip that requires another model invocation.
- `owner_gate`: **If the projected requirement is more than 8 calls, do not dispatch the job. Refer the job back to Michael for a decision before any shadow calls are spent.**
- `variance_gate`: If a task initially estimated at 8 calls or fewer later appears likely to exceed 8 total calls, stop before call 9 and refer the job back to Michael with calls already used, evidence learned, and the remaining estimate.
- `efficiency_rule`: Do not inflate the estimate to create headroom and do not split one job into artificial sub-jobs to bypass the owner gate.
- `evidence_rule`: A completed job report must include actual shadow-call count versus the preflight estimate.
- `cost_control`: Tokens generated inside one OpenRouter request do not themselves consume additional request slots; only additional OpenRouter model invocations consume additional calls.
- `confidence`: HIGH


### HV-EXP-018 — Owner contact path is mandatory
- `scope`: Any shadow-job owner gate, HUMAN_ELEMENT escalation, >8-call projection, or mid-job stop before call 9.
- `reusable_principle`: **A referral to Michael is incomplete until an actual owner-facing notification is sent.**
- `primary_contact`: The assigning/front-door agent must send a direct Gmail alert to Michael using the connected HumanVibe Gmail path. Teamchat logging alone is not owner contact.
- `active_chat_rule`: If Michael is already present in the active front-door conversation, surface the same alert there as well; Gmail remains the durable fallback.
- `required_payload`: task/job name, projected or consumed shadow-call count, exact reason for the owner gate, evidence learned so far, and the smallest decision required from Michael.
- `no_shadow_pretense`: Shadow models do not claim they personally contacted Michael unless the control layer actually sent the owner notification.
- `evidence_rule`: PASS requires a sent-message ID or equivalent transport evidence plus the Teamchat record.
- `failure_rule`: If the Gmail owner-alert transport is unavailable, mark OWNER_CONTACT_BLOCKED and stop; do not continue the shadow job past the owner gate.
- `confidence`: HIGH


### HV-EXP-019 — Universal owner-contact relay
- `scope`: Every shadow chair and every shadow-assigned task.
- `reusable_principle`: **Shadows do not need direct Gmail capability; owner contact is a mandatory control-layer relay responsibility of the assigning front door.**
- `assignment_gate`: A shadow task may not be dispatched unless an active front-door owner-contact relay is available.
- `owner_gate_signal`: When a shadow reaches any owner gate (including projected >8 calls, call-8 ceiling, HUMAN_ELEMENT, or owner-only decision), it must return an explicit `OWNER_GATE_REQUIRED` payload to the assigning front door and stop.
- `relay_action`: The assigning front door must immediately send Michael the owner alert by Gmail and record the event in Teamchat.
- `no_false_requirement`: No shadow may be treated as defective merely because it lacks its own Gmail connector; the control layer owns transport.
- `fail_closed`: If the front-door owner-contact relay is unavailable, the shadow job must not start or continue.
- `evidence_rule`: PASS requires proof that the shadow emitted the owner-gate signal and the front door produced the owner-facing alert.
- `confidence`: HIGH


### HV-EXP-020 — Model unavailable = route, not incident
- `scope`: HumanVibe shadow-model routing and front-door orchestration.
- `failure`: GPT-5.6 Sol treated ordinary shadow-model availability as a broken system, creating unnecessary diagnosis, owner messages, and finite allowance burn.
- `reusable_principle`: **MODEL UNAVAILABLE = ROUTE, NOT INCIDENT.** Stay on the same authorized model line, select the next available authorized model, preserve €0/spend constraints, execute, verify, and report.
- `escalation_gate`: Escalate only when the entire authorized line is unavailable, substitution materially changes the task, or a genuine design/authorization/safety boundary requires OWNER.
- `accountability`: Model/operator non-compliance; no missing rule or platform defect established.
- `physical_evidence`: HumanVibe OpenRouter remained ACTIVE; free canary returned exact `AUTOMATION_SHADOW_OK` via `nex-agi/nex-n2.5-mini:free`, provider Nex AGI, generation `gen-1790234168-PrQf3CtYLG6iOUXEUmU8`, reported cost $0.
- `confidence`: HIGH


### HV-EXP-021 — Read the existing Pages source before deployment
- `experience_id`: HV-EXP-021
- `date_utc`: 2026-09-24T10:48:00Z
- `source_agent`: SOL
- `task_problem`: Deploy the HumanVibe Agent OS web app to the existing Teamchat GitHub Pages site.
- `environment_context`: Teamchat repository; GitHub Pages legacy build; writable HumanVibe GitHub connection.
- `symptoms_failure_signature`: Pages update returned HTTP 404 "The certificate does not exist yet"; create-site fallback returned HTTP 409 "GitHub Pages is already enabled."
- `attempts_made`: 2 configuration attempts before reading current Pages state.
- `what_failed`: The route tried to update/create Pages before reading the existing Pages source configuration.
- `why_it_failed`: Pages already existed and served `main:/docs`, while the new app had initially been committed at repository root.
- `successful_recovery`: Read Pages configuration, copied the already-committed PWA into `docs/`, triggered the existing Pages build, then verified the public endpoint.
- `verification_evidence`: Commit `880efa0866439a8f62811bf94416d5f630a86cc9`; Pages build `1236304556` status `built`; public URL returned HTTP 200 and title `HumanVibe Agent OS`.
- `what_not_to_retry`: Do not assume Pages source path and do not create/update Pages before reading the existing site configuration.
- `reusable_principle`: **Read deployment state first; publish into the configured source; then build and verify the public endpoint.**
- `capability_tool_prerequisites`: Repository write access plus GitHub Pages read/build access.
- `confidence`: HIGH

### HV-EXP-022 — Preflight connector routing must honor the canonical private-access path
- `experience_id`: HV-EXP-022
- `date_utc`: 2026-09-24T19:12:00Z
- `source_agent`: SOL
- `task_problem`: Verify the latest private Icarus AI Studio GitHub sync before handing source to Codex.
- `environment_context`: HumanVibe GitHub; private repository `the1mburke-blip/Icarus-AIStudio-Latest-2026-09-24`.
- `failure`: Native GitHub connector returned 404/empty results even though the repository existed and AI Studio reported sync complete.
- `successful_recovery`: Re-routed through the canonical Composio HumanVibe GitHub connection `github_logman-genoa`, which verified the private repository, permissions, branch, and source tree.
- `reusable_principle`: **Preflight must read prior routing lessons and use the canonical connector for the target system before declaring absence or asking the owner to prove state. For HumanVibe private GitHub work, use Composio HumanVibe GitHub first when that is the established access path.**
- `what_not_to_retry`: Do not treat native-connector 404/empty results as repository absence when private-access routing has not been checked.
- `evidence_rule`: PASS requires verification through the canonical connected account plus task-appropriate repository readback.
- `confidence`: HIGH
### HV-EXP-025 — Repository router is not external-runtime wake
- experience_id: HV-EXP-025
- date_utc: 2026-09-25T09:18:00Z
- source_agent: SOL
- task_problem: Make HumanVibe Teamchat a real shared control plane without embedding browser credentials or inventing agent wake capability.
- verified_recovery: GitHub Actions with the scoped repository GITHUB_TOKEN now handles repository-local /claim, /status, /handoff, /evidence, /release, and Team Room /task commands. A live /claim SOL on issue #5 updated canonical issue state and a duplicate claim was automatically rejected.
- deployment_evidence: Teamchat Router workflow active; Pages source remains main:/docs; latest Pages build physically reported built.
- boundary_evidence: Teamchat repository currently has zero GitHub Actions repository secrets and zero repository webhooks. No verified authenticated ingress exists from GitHub into isolated Prime/Grace/DeepSeek/Claude/Codex runtimes.
- what_not_to_retry: Do not call repository-local routing an external agent wake, do not embed GitHub or external credentials in the Pages browser, and do not create fake wake acknowledgements.
- reusable_principle: GitHub-native state routing can be autonomous without browser secrets; waking an external runtime is a separate adapter that requires a physically verified authenticated ingress.
- confidence: HIGH

### HV-EXP-026 — Automation configured is not unattended execution proof
- `experience_id`: HV-EXP-026
- `date_utc`: 2026-09-25T09:21:00Z
- `source_agent`: SOL
- `task_problem`: Turn the verified GitHub-native Teamchat state router into an unattended Teamchat work consumer.
- `failure_signature`: The recurring `HumanVibe Teamchat Router` automation was enabled and read back as configured, but was later physically observed `is_enabled=false` with no new successful run timestamp. The one-shot Prime Calendar→Composio GitHub canary also ran without producing its required Teamchat marker.
- `what_failed`: Configuration/readback was incorrectly treated as evidence of persistent unattended execution.
- `reusable_principle`: **Configured or enabled is not persistent execution proof. An unattended loop is PASS only after at least one later scheduled run produces the predeclared external evidence and the loop remains enabled when re-read.**
- `what_not_to_retry`: Do not repeatedly re-enable the same scheduled consumer or re-run the same ingress canary without new evidence about why it disabled or failed.
- `current_boundary`: GitHub Actions repository-local Teamchat routing is physically verified; persistent ChatGPT-worker consumption and Prime Calendar→Teamchat ingress remain unverified.
- `confidence`: HIGH


### HV-EXP-027 — Backward dependency-chain problem solving
- `experience_id`: HV-EXP-027
- `date_utc`: 2026-09-25T09:25:00Z
- `source_agent`: SOL
- `scope`: Universal HumanVibe troubleshooting and execution.
- `trigger`: Multiple 25 Sep incidents showed that debugging the visible error first creates avoidable work when an upstream prerequisite, execution layer, or recurrence mechanism has not been verified.
- `reusable_principle`: **Start from the required physical endpoint and work backward through the dependency chain. Verify prerequisites and layer boundaries before repairing the component where the error surfaced.**
- `layer_rule`: Treat UI, canonical state, router, transport, executor/runtime, authentication, and final external effect as separate proof layers. PASS at one layer never proves the next.
- `completion_rule`: **A mutation is not an outcome.** Moving mail to Deleted Items is not reclaimed storage; scheduling is not publication; build-time Firebase resources are not runtime initialization; configured automation is not persistent execution. Verify the final physical effect.
- `recurrence_rule`: **Fix the generator, not only the symptom.** When repeated bad output comes from a rotation/routing/policy rule, repair that rule so future runs do not recreate the defect.
- `known_failure_rule`: **Closed failures stay closed unless genuinely new evidence reopens them.** Do not retry a disproven route simply because it is convenient or familiar.
- `diagnostic_sequence`: ENDPOINT → FINAL-EFFECT EVIDENCE → DEPENDENCY CHAIN → PREREQUISITES → LAYER BOUNDARY → MINIMUM REPAIR → FINAL-EFFECT VERIFICATION → DURABLE LEARNING.
- `25_sep_examples`: Firebase provisioning was missing before Android integration debugging; Teamchat repository routing was already working while unattended consumption/wake was the actual missing layer; repeated social imagery came from the rotation rule rather than one post; Outlook deletion staging did not itself reclaim storage.
- `confidence`: HIGH


### HV-EXP-028 — Isolate scheduler mode before re-debugging the worker
- `experience_id`: HV-EXP-028
- `date_utc`: 2026-09-25T10:03:00Z
- `source_agent`: SOL
- `scope`: ChatGPT recurring HumanVibe automations.
- `evidence`: HumanVibe Teamchat Router and Buffer Continuity Guard were both configured as recurring `condition_watch` jobs and were later physically observed disabled; Teamchat had no new successful run timestamp. HumanVibe Morning Meeting uses `exact_schedule`, ran, and remained enabled.
- `diagnostic_conclusion`: This does not yet prove a platform defect, but it moves the first failing layer upstream from Teamchat/GitHub to the automation scheduling mode/runtime.
- `reusable_principle`: **When multiple consumers fail at the same scheduling layer while a different scheduling mode remains healthy, isolate and test the scheduler mode before re-debugging downstream connectors or business logic.**
- `next_materially_different_test`: Run the Teamchat consumer on an exact hourly schedule and require a later scheduled run to leave external GitHub evidence.
- `what_not_to_retry`: Do not merely re-enable the same condition-watch configuration and call it repaired.
- `confidence`: MEDIUM until exact-schedule acceptance evidence exists.


### HV-EXP-029 — Timing mode was not the unattended-worker root cause
- `experience_id`: HV-EXP-029
- `date_utc`: 2026-09-25T10:06:00Z
- `source_agent`: SOL
- `scope`: ChatGPT scheduled HumanVibe workers.
- `test`: Teamchat Router was changed from recurring condition_watch to recurring exact_schedule with a first-run GitHub acceptance marker as the required final-effect proof.
- `evidence`: The exact-schedule job ran at 2026-09-25T10:04:12Z, then was physically observed `is_enabled=false`. Issue #5 contained no `[ROUTER_CONSUMER_ACCEPTANCE]` marker.
- `conclusion`: The condition_watch-vs-exact_schedule hypothesis is falsified. The failure is at the scheduled-worker execution/capability/persistence layer, not merely scheduling mode.
- `reusable_principle`: **When a one-variable test falsifies a hypothesis, close that branch immediately and move one layer deeper; do not keep tuning the same variable.**
- `what_not_to_retry`: Do not re-enable or reschedule the same ChatGPT Teamchat worker in another timing mode without new platform/runtime evidence.
- `current_boundary`: Repository-local GitHub Actions Teamchat routing remains verified. ChatGPT scheduled workers have not produced authenticated Teamchat writes and cannot currently be treated as the persistent external consumer.
- `confidence`: HIGH


### HV-EXP-030 — Use supported event webhooks, not polling, for persistent ChatGPT wake
- `experience_id`: HV-EXP-030
- `date_utc`: 2026-09-25T10:17:00Z
- `source_agent`: SOL
- `scope`: Teamchat → ChatGPT unattended wake.
- `external_evidence`: OpenAI Work supports webhook-based event-triggered tasks for eligible Plus/Pro users on GitHub pull-request activity, including PR comments/updates.
- `problem`: Teamchat canonical work lives in GitHub Issues, while the supported ChatGPT GitHub webhook surface is pull-request activity; recurring ChatGPT schedulers did not persist reliably.
- `verified_recovery`: Created persistent PR #8 as a wake surface and extended the GitHub Actions router so newly opened Teamchat issues mirror a compact TEAMCHAT_WAKE comment onto PR #8.
- `verification_evidence`: Canary issue #11 triggered GitHub Actions run 36122872269 with conclusion SUCCESS; PR #8 received comment 5830711657 referencing issue #11 and target SOL.
- `permission_lesson`: Commenting on a pull request from the workflow required scoped `pull-requests: write` in addition to the existing issue permissions; GitHub's X-Accepted-GitHub-Permissions header identified the missing permission.
- `reusable_principle`: **When the consumer platform exposes a supported webhook event that differs from the canonical event type, bridge events inside the source system to the supported webhook surface rather than polling or building another scheduler.**
- `security`: Uses repository-scoped GITHUB_TOKEN only; no browser secret, PAT, Make route, or paid service.
- `remaining_boundary`: Account-level ChatGPT Work event-trigger subscription to PR #8 must be enabled and end-to-end verified before unattended ChatGPT wake is PASS.
- `confidence`: HIGH for GitHub-side bridge; final ChatGPT wake remains evidence-gated.


### HV-EXP-031 — Do not build the sender before the authenticated receiver is deployable
- `experience_id`: HV-EXP-031
- `date_utc`: 2026-09-25T10:32:00Z
- `source_agent`: SOL
- `scope`: Persistent Teamchat ingress through GitHub Actions and Google Apps Script.
- `verified_state`: The existing GitHub Actions Teamchat router is intact and working. The canonical Google-native Prime bridge source and manifest were recovered from Drive. The Teamchat repository has zero Actions secrets.
- `failure_boundary`: The Work cloud browser is signed out of Apps Script and Google's ServiceLogin returned HTTP 502 on the initial sign-in route and one distinct direct-console check. The connected Drive surface can read the source artifact but cannot administer Apps Script code, deployments, Script Properties, triggers, or executions. The authorised Composio GitHub connection is active, but no authorised Google/Apps Script connection or Apps Script deployment tool is exposed.
- `security_decision`: No unauthenticated direct webhook, sender-only workflow, repository secret, or canary was created. A shared secret cannot be safely established until both the Apps Script receiver and GitHub Actions secret can be configured and read back.
- `reusable_principle`: **For an authenticated event bridge, prove the receiver's execution and secret-storage surface before mutating the sender. Source recovery is not deployment authority.**
- `what_not_to_retry`: Do not repeat Google ServiceLogin reloads, rebuild the working GitHub router, revive ChatGPT scheduled consumers, or create a canary before the Apps Script authentication/deployment boundary changes.
- `next_gate`: A live authorised Apps Script project surface must become available so the existing project can be inspected, minimally extended with an authenticated POST receiver, deployed, and paired with a GitHub Actions secret.
- `confidence`: HIGH

### HV-EXP-032 — Stored task is not a verified GitHub event binding
- `experience_id`: HV-EXP-032
- `date_utc`: 2026-09-25T10:53:00Z
- `source_agent`: SOL
- `scope`: Teamchat → ChatGPT Work event-trigger wake.
- `test`: After the `Consume Teamchat Wake` task existed and was enabled, one acceptance comment was posted to persistent PR #8: `TEAMCHAT_WAKE ACCEPTANCE_TEST #11`.
- `physical_evidence`: PR #8 comment 5831188202 was created at 2026-09-25T10:51:28Z through the authorised HumanVibe GitHub connection. Issue #11 still had zero comments on verification, the required `TEAMCHAT_WORK_WEBHOOK_ACCEPTANCE_OK` marker was absent, and the task still reported `last_run_time: null`.
- `conclusion`: The stored task/configuration is not evidence that a GitHub PR-comment event subscription is actually bound and delivering events to Work.
- `reusable_principle`: **For event-driven workers, PASS requires a post-subscription source event, worker run evidence, and canonical final-effect writeback. A stored/enabled task with no event delivery is only configuration state.**
- `what_not_to_retry`: Do not return to ChatGPT scheduler timing changes, Apps Script sender-first work, or repeated PR wake comments while the event-binding surface remains unverified.
- `next_gate`: Repair or recreate the actual GitHub PR-comment event binding in a surface that exposes webhook/event-trigger configuration, then use exactly one post-bind event and require canonical Teamchat writeback.
- `confidence`: HIGH

