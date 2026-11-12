# Four-day blocker rule trial — 12–15 November 2026

- **Proposed / authorised by:** Michael, 12 November 2026 (ChatGPT conversation).
- **Repository recorder / executor:** GPT-6 via authorised Teamchat GitHub connector; this is a scoped documentation change, not a claim to act as Codex, Claude, Saul, Gemini, or another agent.
- **Trial period:** 2026-11-12T00:00:00Z through 2026-11-15T23:59:59Z. **Expires:** 2026-11-16T00:00:00Z. Review on 16 November.
- **Purpose:** Test whether failure-triggered diagnosis and evidence-led alternatives improve honest task completion without token-burning repeat loops or false PASS claims.
- **Scope:** Executable tasks whose agent/runtime actually retrieves this policy. The trial does not silently change model weights, separate chats, deployed Fixer containers, system prompts, credentials, permissions, GitHub branch protection, budgets, or production workflows.
- **Safety / spend:** €0 incremental paid spend; no unapproved production mutation, credentials, authorisation escalation, extra autonomous dispatch, or unnecessary tests. Existing higher-priority restrictions and all other operating rules remain effective.
- **Activation criterion:** Rule amendment merged onto protected `main`, read back, and shown to have been retrieved by the relevant executor before its task. A PR alone is not activation or proof of changed behaviour.
- **Reversibility:** The amendment is explicitly time-bound and ceases to apply after expiry even if the historical text remains. Review may separately recommend continuing, revising, or retiring it; extension requires fresh authorisation.

## Exact governing sequence

**FAIL → LEARN → RETRY ALTERNATIVES → GROW → SUCCEED**

1. **FAIL:** Identify the exact observed failure and preserve the error, logs, prior attempt, and task identity. Failure is an event, not an automatic exit; do not invent progress.
2. **LEARN:** Investigate the cause or strongest evidence-supported explanation, including relevant earlier attempts. State specifically what needs to change for the next attempt to have a better prospect of success.
3. **RETRY ALTERNATIVES:** Execute an authorised alternative that **directly addresses what was learned in Step 2**. Record the causal link: lesson → targeted change → new result. On failure, update the diagnosis from the new evidence before choosing another approach. Do not list alternatives as a substitute for executing one, blindly retry unchanged methods, or spend allowance against already disproven routes.
4. **GROW:** Apply the verified new knowledge to the next action and reusable task record. A learning document alone is not task completion; continue toward the original acceptance criteria.
5. **SUCCEED:** Independently verify the physical final effect against the original, unchanged acceptance criteria. Only then report PASS.

### Outcome and accountability separation

- **PARTIAL ≠ PASS.** Incomplete work remains incomplete. During the trial, truthful PARTIAL / BLOCKED reporting is not, by itself, an integrity offence or permission to abandon the objective.
- **False PASS = integrity violation.** A completion claim without independent final-effect evidence is noncompliant even if the intermediate implementation appears plausible.
- **Task ownership persists.** After failure, pursue evidenced repairs and legitimate alternative routes, subject to authorisation and budget. Do not secretly narrow scope, change executor/endpoint, omit acceptance gates, or self-certify another agent's identity.
- **Boundaries remain real.** Stop execution and expose the exact blocker when a safety/security/permission/owner-only boundary is reached, or when evidence shows every reasonably available authorised route exhausted. Record the specific investigated routes and why further attempts would be blind; the task is still not PASS.
- **No repeat loops.** Every retry must name the new observation or changed hypothesis and the corresponding corrective action; an unchanged failure signature without new evidence blocks that retry. Re-preflight on material route, cost, authority or scope change.

## Minimal evidence per actual failure (reuse existing task log; no dummy incidents)

| Field | Required content |
| --- | --- |
| task_id / executor / date_utc | Real task, authenticated executor identity if available, timestamp |
| original_acceptance | Unchanged requested result and PASS proof |
| failure_evidence | Raw error, link/log/source; label missing evidence |
| learning | Cause or uncertainty and what must change |
| targeted_alternative | New authorised action explicitly tied to learning |
| retry_result | Tool/process readback; whether it altered diagnosis |
| task_result | PASS / PARTIAL / BLOCKED / FAIL with supporting independent evidence |
| cost_and_calls | Observed spend/usage or clearly marked unavailable |
| owner_intervention | Count and reason if actually required |

## Evaluation on 16 November 2026

Compare **eligible observed failures** and follow-on task executions during the trial with available 9–11 November records. Do not invent a baseline or claim a controlled experiment; normal workload and tool availability differ. Report counts and trace links for:

1. Failures with an explicit evidence-supported lesson.
2. Failures followed by a *performed*, causally targeted alternative (not merely suggested).
3. Blind or identical retries, including token/request burn when measurable.
4. Unsupported PASS or misleading executor/completion claims.
5. Verified outcomes per eligible task and unresolved BLOCKED/PARTIAL outcomes.
6. Avoidable owner interventions and owner-only boundaries.
7. Whether the relevant runtime actually retrieved the amendment; count non-ingesting agents separately.

**Decision:** Keep, modify, or discontinue only on observed task evidence. No claimed model improvement merely because this file exists.

## Preflight and known historical lessons

- Scanned: `OPERATING_RULES.md`, `MICHAEL_USER_GOVERNANCE.md`, `TRAINING_MATRIX.md`, `icarus/memory/learned.md`, `icarus/memory/current-state.md`, and the 5 Nov owner/ChatGPT contract record.
- Historical failure signatures: premature PASS, WORK/Codex identity conflation, narrow reading of instructions, unsupported blocker explanations, unproductive retries, preflight expense, and runtime-ingestion gaps.
- The changes add **no** new executor rights, permanent duty loop, code tests, production changes, or automatic claims of compliance. The established twelve-rule and preflight checks remain mandatory wherever applicable.
- Trial endpoint: documented, time-limited policy on `main` and a separately executed 16 Nov evidence review. External monetary cost ceiling €0; exact model-token consumption unavailable.
