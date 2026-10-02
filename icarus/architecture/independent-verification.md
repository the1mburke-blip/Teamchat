# Icarus — Blocker 8: Independent final-effect verification

- date: 2026-10-02
- status: RESOLVED_ARCHITECTURALLY
- applies_to: Android Composio hands and desktop DSH hands

## Blocker
A model, tool, API wrapper, or executor returning success is not proof that the requested real-world effect occurred. The executor must not self-certify PASS.

## Decision
Every mutating Icarus task must carry an Effect Contract before execution and run a separate verification phase after execution.

## Effect Contract
Before a write, Icarus records:
- task_id
- intended external effect
- target resource/account
- mutation fingerprint / idempotency key
- expected observable postcondition
- verification read path
- allowed verification delay/window
- rollback or reconciliation rule if applicable

## Execution state machine
PLANNED
-> AUTHORIZED
-> EXECUTING
-> OUTCOME_UNKNOWN or VERIFYING
-> PASS / FAIL / UNCLEAR

Tool success never jumps directly to PASS.

## Verification phase
1. Use a read-only Composio tool or authenticated provider read endpoint distinct from the mutation call.
2. Retrieve the actual target state.
3. Compare actual state to the Effect Contract.
4. Persist evidence reference/hash.
5. PASS only if the required postcondition is physically observed.
6. If the write may have happened but readback is inconclusive, mark UNCLEAR/OUTCOME_UNKNOWN and reconcile before any retry.
7. FAIL when the target state contradicts the requested effect.

## Verifier independence
The same reasoning model may prepare the contract, but it does not decide PASS by narration.
PASS is produced by deterministic comparison of readback evidence wherever possible.

For effects requiring semantic interpretation, use a separately invoked verifier step/model with only:
- requested effect
- verification criteria
- readback evidence
It receives no executor self-assessment.

## Evidence receipt
Each completed task stores:
- task_id
- action timestamp
- provider/tool used
- external resource identifier where safe
- verification timestamp
- observed postcondition
- evidence hash/reference
- terminal state

## PASS gate
A controlled test must show:
1. executor returns success while external effect is deliberately absent -> Icarus refuses PASS.
2. executor succeeds and readback matches -> PASS.
3. timeout/unknown mutation outcome -> no duplicate retry until reconciliation.
