# HumanVibe Handoff and Routing Protocol

## One issue, one work item

Create or reuse exactly one GitHub Issue for each executable task. Before creating a new Issue, search open and closed Issues for the same objective.

## Required issue title

`[TIER] [STATUS] Short task name`

Example: `[T1] [REQUESTED] Verify storefront checkout`

## Required task header

```text
[TIMESTAMP] <ISO-8601 UTC>
[FROM] [LUNA] | [SOL] | [PRIME] | [GRACE] | [DEEPSEEK]
[TO] [LUNA] | [SOL] | [PRIME] | [GRACE] | [DEEPSEEK]
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

## Deterministic escalation

- Per free chair: maximum 7 educated attempts on the same task; retain 3 calls from a 10-call daily allocation as protected reserve.
- Luna attempt 7 FAIL/BLOCKED after genuine learning → HANDOFF_TO: SOL with all seven failure records.
- SOL must ingest the full Luna packet and shared training before SOL attempt 1.
- SOL attempt 7 FAIL/BLOCKED after genuine learning → HANDOFF_TO: OWNER with the consolidated Luna + SOL record.
- OWNER chooses any further chair or route.
- Hard capability blockers escalate immediately; do not burn the remaining attempt budget proving the same blocker.
- HUMAN_ELEMENT blockers bypass the ladder and route directly to OWNER immediately.
- No lateral chair hopping and no executing-chair self-downgrade around this rule.

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
HANDOFF_TO: LUNA | SOL | PRIME | GRACE | DEEPSEEK | OWNER | NONE
```

A handoff is accepted only when the receiving agent posts a new `CLAIMED` entry. Until then, the current owner remains responsible.

If allowance use materially exceeds the job-start estimate, stop and re-preflight before continuing.

## Completion

PASS requires evidence and a final duplicate/regression check. The active owner posts the terminal comment, removes active ownership, records final allowance usage, appends a concise outcome to `CHAT_LOG.md`, and adds any reusable verified lesson to `TRAINING_MATRIX.md`.

## Supersession

Do not edit history to hide obsolete instructions. Add a new `SUPERSEDED` entry citing the superseded Issue/comment and replacement authority.
