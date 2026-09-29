# HumanVibe Handoff and Routing Protocol

## One issue, one work item

Create or reuse exactly one GitHub Issue for each executable task. Before creating a new Issue, search open and closed Issues for the same objective.

## Required issue title

`[TIER] [STATUS] Short task name`

Example: `[T1] [REQUESTED] Verify storefront checkout`

## Required task header

```text
[TIMESTAMP] <ISO-8601 UTC>
[FROM] [LUNA] | [SOL] | [PRIME] | [DEEPSEEK]
[TO] [LUNA] | [SOL] | [PRIME] | [DEEPSEEK]
[STATUS] REQUESTED
[ACTIVE_OWNER] NONE
[OBJECTIVE] One testable endpoint
[SCOPE] Systems and actions authorised
[PROTECTED] Systems that must not change
[COST] €0
[ALLOWANCE_BUDGET] Estimated tokens, requests, or allowance percentage
[EVIDENCE_REQUIRED] Physical/readback proof required for PASS
```

## Claim / mandatory job-start attestation

The assigned agent rechecks for an active owner, then comments:

```text
[SOL] <ISO-8601 UTC>
STATUS: CLAIMED
ACTIVE_OWNER: SOL
MODEL_CHAIR: exact model/runtime occupying the chair
DUPLICATE_CHECK: PASS
HISTORY_REVIEW: PASS — own logs + relevant prior-team attempts reviewed
TRAINING_REVIEW: PASS — relevant TRAINING_MATRIX.md entries reviewed
TRAINING_QUOTE: "<one verbatim task-relevant line from TRAINING_MATRIX.md>"
TRAINING_SOURCE: <lesson ID or section heading>
TRAINING_RELEVANCE: <one sentence explaining why this lesson applies to this task>
KNOWN_FAILURES: concise failure signatures / what-not-to-retry, or NONE FOUND
ALLOWANCE_ESTIMATE: <estimated tokens, requests, or allowance %>
NEXT: Execute the authorised objective.
```

Only the active owner executes. Other agents may add evidence or critique but must not duplicate execution.

A claim is incomplete for every executable task until both `HISTORY_REVIEW` and `TRAINING_REVIEW` are complete, the relevant training quote/source/relevance are present, and allowance usage has been estimated. Native model memory is not accepted as a substitute. A generic or unrelated training quote is a failed start gate. Do not enter EXECUTING until the complete attestation exists.

Before the first execution attempt, the active owner must review relevant prior attempts and shared training entries and carry forward known failure signatures, causes, successful recoveries, and do-not-retry evidence.

After any failed attempt, capture the failure durably before retrying. If the failure creates reusable knowledge, append a verified entry to `TRAINING_MATRIX.md`. The next attempt must be materially different or supported by new evidence.

## Free-shadow and deterministic escalation

- Read `FREE_CHAIRS.md` and route first to the matching `(or)` shadow when the task is eligible for free inference.
- Each `(or)` shadow gets at most 7 educated attempts on the same task; calls 8–10 of a nominal 10-call allocation remain protected reserve.
- Every failed attempt is captured before another call and must materially change the next approach.
- On shadow attempt 7 failure, hand the complete learning packet vertically to the named premium counterpart:
  - `Luna(or) → Luna`
  - `Sol(or) → Sol`
  - `Gemini(or) → Gemini`
  - `DeepSeek(or) → DeepSeek`
  - `Claude(or) → Claude`
- The premium counterpart must ingest the full shadow packet and Training Matrix before premium attempt 1.
- Premium chairs use the same learning discipline and maximum 7-attempt cycle before the established higher-chair/OWNER escalation.
- OpenRouter Free is a shared 50-request/day pool. Five shadows × 7 task attempts = 35 possible task attempts if all five are legitimately engaged, leaving 15 shared reserve calls.
- A hard capability/authentication blocker escalates immediately.
- A HUMAN_ELEMENT blocker bypasses all model attempts and routes directly to OWNER.
- Free endpoints must be revalidated as free before use. No paid OpenRouter fallback is permitted.

## Progress and handoff

Use one comment per meaningful state change:

```text
[PREFIX] <ISO-8601 UTC>
STATUS: EXECUTING | VERIFYING | PARTIAL | BLOCKED | FAIL | PASS
ACTION: What was actually done
EVIDENCE: Current evidence
CHANGES: Exact mutations
BLOCKER: NONE or exact dependency
ALLOWANCE_USED: <actual measured usage, or clearly labelled estimate>
NEXT: One next action
HANDOFF_TO: LUNA | SOL | PRIME | DEEPSEEK | OWNER | NONE
```

A handoff is accepted only when the receiving agent posts a new `CLAIMED` entry. Until then, the current owner remains responsible.

If allowance use materially exceeds the job-start estimate, stop and re-preflight before continuing.

## Completion

PASS requires evidence and a final duplicate/regression check. The active owner posts the terminal comment, removes active ownership, records final allowance usage, appends a concise outcome to `CHAT_LOG.md`, and adds any reusable verified lesson to `TRAINING_MATRIX.md`.

## Supersession

Do not edit history to hide obsolete instructions. Add a new `SUPERSEDED` entry citing the superseded Issue/comment and replacement authority.


## Hard pre-call gate

This gate applies to every model and every executable invocation, including canaries, tests, retries, and verification calls.

Before call 1, the active chair must record:
- `HISTORY_REVIEW: PASS`
- `TRAINING_REVIEW: PASS`
- `TRAINING_QUOTE`
- `TRAINING_SOURCE`
- `TRAINING_RELEVANCE`
- `KNOWN_FAILURES`
- `MODEL_CHAIR`
- `ALLOWANCE_ESTIMATE`

The chair must search the Training Matrix and relevant prior logs for matching provider, tool, system, and failure signatures. If a known failure exists, it must be surfaced before execution and the proposed route must account for it.

**No attestation = no call.** This is not discretionary and cannot be bypassed by calling the task trivial, treating it as a canary/test, or relying on native model memory.

## DeepSeek utilization profile — full-model chair

Use the full DeepSeek seat as an **analytical reasoning, research, red-team, and bounded specialist-execution chair**. Deterministic repository/runtime state remains authoritative; DeepSeek does not become the control plane.

Preferred routes:
- cross-document/log synthesis from sanitized text packets;
- skeptical/red-team review and strongest-counterargument generation;
- DISCUSS → DISPROVE support: claim / evidence / counterevidence / unresolved-proof matrices;
- self-critique passes that enumerate assumptions, missed edge cases, and disconfirming evidence;
- structured JSON/Markdown outputs for downstream routing;
- prompt design, adversarial test generation, checklists, pre-mortems, and other meta-work;
- surgical refinement of a specific weak section rather than full regeneration;
- layered explanation when the team needs plain-language, technical, and implementation-level views.

Capability gates:
- Do not assume memory survives separate wake/model runs; pass explicit state/context.
- Do not assume image input or multimodal analysis until that exact runtime/path is proven.
- Do not assume native file access; supply bounded sanitized extracts or proven file inputs.
- DeepSeek self-verification is advisory. Repository/runtime state and physical endpoint evidence remain authoritative.
- Do not send secrets, owner-private data, credentials, or protected customer data.
- Irreversible mutations and authenticated execution require a chair/runtime with the proven tool authority.

Routing rule: route analytical reasoning, research, adversarial review, synthesis, and suitable bounded specialist execution to the full DeepSeek chair when its current runtime has the required capability. Do not conflate this chair with the separate self-hosted R1-distill persistence ghost documented in historical training.



## Twelve-rule governance gates

Every substantive task must pass three separate immutable-rule checks.

### Gate 1 — preflight rule weighting

Before route selection or substantive execution, record all 12 canonical immutable rules:

```text
RULE_WEIGHTING:
R1: <rule name> | WEIGHT: CRITICAL|HIGH|MEDIUM|LOW|N/A | WHY: <task-specific reason>
R2: ...
...
R12: ...
RULE_WEIGHTING_STATUS: PASS
```

All 12 entries are mandatory. `N/A` requires an explicit reason. Missing weighting = `PREFLIGHT NOT READY`.

### Gate 2 — mapped-route compliance review

Once the exact route has been mapped—executor, tools, dependencies, cost, owner boundary, evidence path, and blocker conditions—but before the first substantive execution, review that route against the weighted rules:

```text
ROUTE_COMPLIANCE_REVIEW:
R1: PASS|FAIL | EVIDENCE/CONTROL: <how the mapped route complies>
R2: ...
...
R12: ...
ROUTE_COMPLIANCE_STATUS: PASS|FAIL
```

A FAIL on any `CRITICAL` or `HIGH` rule blocks execution. A material route change invalidates the affected review and requires re-preflight before continuing.

### Gate 3 — separate post-task compliance tracker

When the primary task reaches `PASS | PARTIAL | BLOCKED | FAIL | SUPERSEDED`, create a new compliance-tracker task for that completed run. It is a separate governance work item, not a self-declared note inside the primary task.

Required tracker fields:

```text
[OBJECTIVE] Audit completed task <task/issue/run ID> against all 12 immutable rules
[PRIMARY_RESULT] PASS|PARTIAL|BLOCKED|FAIL|SUPERSEDED
[PRESTART_WEIGHTS] 12-rule weighting snapshot
[ROUTE_REVIEW] 12-rule route-compliance snapshot
[FINAL_COMPLIANCE]
R1: PASS|FAIL|N/A | EVIDENCE: <physical/log evidence> | IMPACT: <if failed>
...
R12: PASS|FAIL|N/A | EVIDENCE: <physical/log evidence> | IMPACT: <if failed>
[SCORE] <rules passed>/<rules applicable>
[MISSES] exact failed rules
[ALLOWANCE_WASTE] measured or explicitly UNVERIFIED
[TRAINING_REQUIRED] YES|NO
[EVIDENCE_REQUIRED] readback proving tracker result and any training write
```

The primary task may be operationally complete, but governance closure is incomplete until this compliance-tracker task reaches a verified terminal state.
