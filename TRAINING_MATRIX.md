# HumanVibe Shared Training Matrix

## Purpose

This is the durable, model-independent experience pool for HumanVibe agents.

A chair does not need built-in memory to benefit from team learning. Before non-trivial execution, the current chair retrieves the relevant entries here plus relevant issue/log history. Verified lessons discovered by one chair become reusable training for every later chair.

**Knowledge belongs to HumanVibe, not to the model occupying the chair.**

## Mandatory retrieval gate

Before the first execution attempt on any non-trivial or previously attempted task:

1. Read the relevant task/Issue and current coordination state.
2. Search this matrix for matching task, system, tool, failure signature, or capability.
3. Review the executing chair's own relevant prior logs when available.
4. Review relevant prior-team attempts.
5. Carry forward verified `what_not_to_retry`, prerequisites, recoveries, and evidence.
6. Record `TRAINING_REVIEW: PASS` before entering EXECUTING.

If no relevant entry exists, record `NONE FOUND`; do not invent prior knowledge.

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
