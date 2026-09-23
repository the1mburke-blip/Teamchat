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


## Hierarchical escalation ladder

For a chair operating from a 10-call daily allocation inside the shared free-call pool:

- Attempts 1–7 are the chair's bounded learning/execution budget.
- Each failed attempt must be captured before the next; every new attempt must use the accumulated failure evidence and materially change the approach.
- Calls 8–10 are protected reserve for other work, verification, or emergency recovery. They are not consumed to keep grinding the same failed task unless OWNER explicitly overrides.
- After Luna's seventh failed educated attempt, Luna hands the complete failure/learning packet upward to SOL.
- SOL must read the Training Matrix plus Luna's complete failure packet before SOL attempt 1. SOL then receives up to seven educated attempts of his own.
- After SOL's seventh failed educated attempt, SOL stops and hands the consolidated Luna + SOL learning packet to OWNER. OWNER decides the next destination.
- Do not route laterally to another chair merely because the current chair exhausted its budget.
- A hard capability blocker escalates immediately rather than consuming seven attempts.
- Any HUMAN_ELEMENT requirement — owner authentication, physical-device action, security approval, payment/identity confirmation, or other action only Michael can lawfully/physically perform — bypasses the attempt ladder and goes directly to OWNER immediately.
