# Pilot build: checkpoint log

This log records review decisions. It is a procedural control: it does not stop an agent from continuing, and it is not runtime enforcement. PASS for any checkpoint belongs to Icarus only. Everything below is PARTIAL until he adjudicates.

Reviews so far were performed by ChatGPT and relayed by the owner. They are not Icarus adjudication.

## Plan (revised 4 Nov 2026 after the ChatGPT reviews)

| # | Checkpoint | Goal |
|---|---|---|
| 1 | PILOT.md fix | Reword rule 1, update stale M2 status |
| 2 | Contract | CONTRACT.md grounded in repo evidence, unverified parts marked PROVISIONAL; this log |
| 3 | Shared authority | session.py: task identity, executor identity, scoped grants, one hash-chained ledger, call state machine with tool-name and exact-argument binding (a mismatch burns the call_id), execution mode, checkpoint plans with mandatory milestone gates (PAUSED_FOR_REVIEW), and signed reviewer decisions (registry, ledger-bound, single-use nonce, SELF_APPROVAL denied, BLOCKED if no vetted Ed25519 verifier). With tests |
| 4 | Model slot | GovernedCore.step() single-step entry point (run() unchanged, 32 governed tests still pass); NullHand for harness mode; OpenAI-compatible endpoint with the wire formats in CONTRACT.md section 3; tests prove no path reaches a reasoner without Core and that tool calls outside the grant are filtered |
| 5 | Hook channel | Default-deny, call_id plus tool-name plus exact-argument matching, owner-only escalation, with tests |
| 6 | Supervisor | Lifecycle control: ownership, termination, crash handling, with tests. Snapshot-diff UNEXPLAINED_CHANGE detection, marked provisional |
| 7 | Fixture integration | Slot + hook + supervisor on one session against a stand-in harness. Fixture only, not acceptance evidence |
| 8 | Adjudicator | require_adjudicator for live mode; full suite run |
| 9 | Repository close-out | Commit and blob-verify every file; live-DSH acceptance script in the repo. Reported PARTIAL |
| 10 | Live harness acceptance | From inside the laptop DSH session: model control, approval, denial, process supervision, evidence persistence. BLOCKED if the real harness is not reachable |

## Decisions

| # | Date | Reviewer | Decision | Evidence | Icarus adjudication |
|---|---|---|---|---|---|
| 1 | 2026-11-04 | ChatGPT (via owner) | Accepted | commit ffbad88c on agent/icarus-core; PILOT.md blob 8f52df2f | none |
| 2 | 2026-11-04 | ChatGPT (via owner) | HOLD, three corrections (v0 commit b9b67d02) | see findings below | none |
| 2 (v0.2) | 2026-11-04 | ChatGPT (via owner) | HOLD, three corrections (commit d9dff2e1) | see second findings section below | none |
| 2 (v0.3) | 2026-11-04 | pending | pending | v0.3 commit: see git log for the commit that touches CONTRACT.md after d9dff2e1 | none |

Review of the original 10-point plan (2026-11-04, ChatGPT): APPROVE WITH REQUIRED CHANGES. Accepted and reflected in the plan: contract grounded in DSH evidence; model slot proven to pass through Core; unknown tools default to deny; supervisor verifies lifecycle and process ownership; checkpoint 10 is real harness acceptance; shared authority across all three surfaces; explicit recorded review decisions.

## Checkpoint 2 HOLD: findings and how each was handled

1. Contract lacked JSON payloads, streaming events and tool-call handling. Agreed. CONTRACT.md v0.2 sections 2 to 5 now give concrete payloads for the session, ledger, chat request, text and tool-call responses, SSE chunks, tool results, errors, hook request/response, escalation and supervisor events. The example JSON blocks were parsed after commit.
2. Core executes tools itself, but the slot returned tool calls for DSH to execute. Agreed, and confirmed in governed.py (run() calls hand.execute() itself). Resolved in CONTRACT.md section 1: one execution mode per session, one executor per call_id, a call state machine, DUPLICATE_EXECUTION and UNPROPOSED_CALL denials, a single-step GovernedCore.step() added at checkpoint 4 without changing run(), and a NullHand that raises in harness mode.
3. max_steps only logs a checkpoint and continues. Partly agreed, partly not changed:
   - That behaviour is the owner's own decision of 29 Oct 2026 (a step count must never end a task, because a count is not an owner-only boundary). It is not changed here. Changing it would reverse a decision only the owner can reverse.
   - The underlying need, an enforced pause/resume gate, is met by a separate opt-in mechanism: owner review gates in the session grant (CONTRACT.md section 2, built at checkpoint 3). Default off. This is marked [DECISION, pending owner confirmation].
   - These build checkpoints are the working procedure of the agent building this. Until checkpoint 3 lands, nothing in code enforces them. The v0.2 contract says so.
   - Detection of ungoverned execution is now marked PROVISIONAL (CONTRACT.md section 6). Harness-reported events are not independent. The planned independent check is a before/after snapshot of scoped paths (UNEXPLAINED_CHANGE), covering file effects only.

## Checkpoint 2 second HOLD (v0.2, commit d9dff2e1): findings and how each was handled

1. Gates must be mandatory for a task with an approved checkpoint plan, and tied to milestones and evidence, not tool-call counts. Agreed. CONTRACT.md v0.3 section 2.1: gates come only from a plan pinned in the session record; a plan cannot be dropped or relaxed inside a session; no plan means an explicit `no_plan` ledger entry; per-milestone grants make a gate impossible to avoid by never declaring a milestone; a declaration needs every required evidence kind (presence only, truth is for the reviewer and the adjudicator); call counts stay a budget.
2. The hook must verify the tool name and exact arguments, not only call_id and scope. Agreed. Section 4: the proposal fixes the tool and a canonical-arguments hash; the hook recomputes it; TOOL_MISMATCH and ARGS_MISMATCH deny and burn the call_id; no fuzzy matching. DSH rewriting arguments is now a checkpoint 10 falsifier.
3. A worker must not resume its own paused session by writing decided_by owner. Agreed. Section 2.3: identity fields are lookup keys only; authority is an Ed25519 signature from a registered reviewer, bound to the session, gate, milestone and ledger head hash, with a single-use nonce; the executor cannot approve (SELF_APPROVAL); no weaker fallback; key custody is an operational requirement that code cannot prove.

Reviewer's answer adopted: step-count logging stays non-stopping, and gates are not default-off when an approved plan exists. Owner confirmation of the review-gate design is still requested.
