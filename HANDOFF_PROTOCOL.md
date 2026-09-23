# HumanVibe Handoff and Routing Protocol

## One issue, one work item

Create or reuse exactly one GitHub Issue for each executable task. Before creating a new Issue, search open and closed Issues for the same objective.

## Required issue title

`[TIER] [STATUS] Short task name`

Example: `[T1] [REQUESTED] Verify storefront checkout`

## Required task header

```text
[TIMESTAMP] <ISO-8601 UTC>
[FROM] [LUNA] | [SOL] | [PRIME]
[TO] [LUNA] | [SOL] | [PRIME]
[STATUS] REQUESTED
[ACTIVE_OWNER] NONE
[OBJECTIVE] One testable endpoint
[SCOPE] Systems and actions authorised
[PROTECTED] Systems that must not change
[COST] €0
[EVIDENCE_REQUIRED] Physical/readback proof required for PASS
```

## Claim

The assigned agent rechecks for an active owner, then comments:

```text
[SOL] <ISO-8601 UTC>
STATUS: CLAIMED
ACTIVE_OWNER: SOL
DUPLICATE_CHECK: PASS
NEXT: Execute the authorised objective.
```

Only the active owner executes. Other agents may add evidence or critique but must not duplicate execution.

## Progress and handoff

Use one comment per meaningful state change:

```text
[PREFIX] <ISO-8601 UTC>
STATUS: EXECUTING | VERIFYING | PARTIAL | BLOCKED | FAIL | PASS
ACTION: What was actually done
EVIDENCE: Current evidence
CHANGES: Exact mutations
BLOCKER: NONE or exact dependency
NEXT: One next action
HANDOFF_TO: LUNA | SOL | PRIME | OWNER | NONE
```

A handoff is accepted only when the receiving agent posts a new `CLAIMED` entry. Until then, the current owner remains responsible.

## Completion

PASS requires evidence and a final duplicate/regression check. The active owner posts the terminal comment, removes active ownership, and appends a concise outcome to `CHAT_LOG.md`.

## Supersession

Do not edit history to hide obsolete instructions. Add a new `SUPERSEDED` entry citing the superseded Issue/comment and replacement authority.
