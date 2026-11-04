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
| 5 to 10 | Replaced | Superseded on 4 Nov 2026 by items B1 to B10 in the Remaining plan section below |

## Decisions

| # | Date | Reviewer | Decision | Evidence | Icarus adjudication |
|---|---|---|---|---|---|
| 1 | 2026-11-04 | ChatGPT (via owner) | Accepted | commit ffbad88c on agent/icarus-core; PILOT.md blob 8f52df2f | none |
| 2 | 2026-11-04 | ChatGPT (via owner) | HOLD, three corrections (v0 commit b9b67d02) | see findings below | none |
| 2 (v0.2) | 2026-11-04 | ChatGPT (via owner) | HOLD, three corrections (commit d9dff2e1) | see second findings section below | none |
| 2 (v0.3) | 2026-11-04 | owner (Michael), in the checkpoint 3 instruction | Accepted | commit 966ef2f5 on agent/icarus-core | none |
| 3 | 2026-11-04 | ChatGPT (via owner) | HOLD, three corrections (commit ecc211ea) | see the HOLD section below | none |
| 3 (rev) | 2026-11-04 | owner (Michael) relaying ChatGPT's verification | Accepted for progression | commit 4bf42185 on agent/icarus-core | none |
| 4 | 2026-11-04 | pending | pending | see the checkpoint 4 section below; commit e07b3859 | none |
| plan | 2026-11-04 | ChatGPT (via owner) | REVISE THE PLAN: replace item 9, strengthen item 10, prerequisite fix | see the revised plan below | none |
| 4 fix | 2026-11-04 | pending | pending | kernel-only PASS no longer writes learning; commit 73a1858d | none |
| DSH docs | 2026-11-04 | ChatGPT (via owner) | PARTIAL; no redesign, keep B1 to B10 | docs read by ChatGPT and again by me; commit in the report | none |

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

## Checkpoint 3 (shared authority): implemented 4 Nov 2026, awaiting review

Built: icarus/agent/pilot/session.py and tests/agent/test_session.py, plus CONTRACT.md v0.4 and this log. No M1 file and no governed.py change. Spend default EUR 0 is enforced and tested.

Owner directive for this checkpoint and where it is enforced:
- The user sets Icarus's objectives and boundaries: the owner-signed Charter, with the owner key pinned.
- Icarus creates and delegates tasks within that authority, without owner approval for routine work: he signs sessions for executing agents, bounded by the charter.
- Agents cannot grant themselves permissions or approve their own work: SELF_GRANT, REGISTRY_FORGED, SELF_APPROVAL, and signatures instead of names.
- Icarus can review delegated work; his own work needs independent verification: independent_verification_required, owner or verifier only.
- Mandatory gates stay enforced for any session with a plan.

Things found and decided while building (not in the accepted contract):
1. Reviewer registry entries must carry the public key, not only a fingerprint, because a fingerprint cannot verify a signature. Contract v0.4 says so.
2. The charter and delegation model did not exist in v0.3. It is now section 2.0 of the contract, taken from the owner's checkpoint 3 directive.
3. Milestone grants inherit call budget, spend and expiry from the session; only tools and path scopes are narrowed. A first draft required them per milestone and failed at session open.
4. State changes happen after the ledger write, so a ledger failure leaves no call behind.

Not built: wiring to GovernedKernel/GovernedCore (checkpoints 4 and 5), ledger resume, the owner's signing tool, any live harness evidence. Status PARTIAL.

## Checkpoint 3 HOLD (commit ecc211ea): findings and how each was handled

1. State changed before the ledger write. Agreed, and confirmed at the cited lines: authorize_execution marked a call EXECUTED and record_result marked it RESULT_RECORDED before writing the entry. Fixed with an explicit ordering rule (contract S8): anything that grants is persisted first; anything that restricts changes state first. The same rule turned up two more cases, both fixed: a decision's nonce was consumed before the decision was logged (now after), and a gate was opened by logging first and pausing second (now pauses first, so a failed write leaves the session paused and blocked, never active). A ledger that fails a write is now marked broken for good, because the file tail is unknown.
2. Argument side files bypassed failure handling. Agreed. A failure saving them is now a controlled denial (SIDE_FILE_FAILED) with nothing authorized; the file is synced, and removed if the ledger write then fails.
3. Kernel enforcement was optional. Agreed. Session.open now refuses to start without a kernel (KERNEL_REQUIRED) unless the caller passes allow_unenforced_kernel, which is recorded in the ledger and makes the session never live_ready. A kernel that raises or answers badly is a denial (KERNEL_ERROR). The kernel's name and reason are written to the ledger for every call. The tests also run the real GovernedKernel through an adapter. Caveat: GovernedKernel counts each authorize call against its own budget and the session asks it twice per call, so its budget must allow for that.
4. Crash resume of the ledger and nonces: agreed, not done here, scheduled as checkpoint 8 (plan row updated). Until then a crash ends the session.

Evidence for the revision: 143 tests in test_session; 40 deliberate breakages of session.py were all caught by the tests, plus one targeted at gate ordering.

## Checkpoint 4 (model slot): implemented 4 Nov 2026, awaiting review

Built: GovernedCore.begin()/step() with StepState/StepOutcome, NullHand and HarnessModeViolation, GovernedKernel.decide() (read-only), icarus/agent/pilot/modelslot.py, Session.log_event and phase-aware kernel calls, plus tests/agent/test_step.py and test_modelslot.py and CONTRACT.md v0.5. run() is byte-for-byte unchanged; no M1 file was edited.

Procedure followed: preflight stated first (read and write to agent/icarus-core only, EUR 0, no live harness); history and training reviewed before building. Lessons applied: HV-EXP-142 (a receipt or an existence check is not proof, so the slot never reports PASS without an independent adjudicator), HV-EXP-146 (acknowledge only after the intake is durable, so the request is logged before the model is asked), HV-EXP-144 (no hand-assembled payloads, so files are committed from a script and read back by blob SHA), HV-EXP-145 (no announcing without acting).

Things found while building, not in the accepted contract:
1. Asking Core's kernel and then the Session's kernel adapter would count each call against the kernel's budget twice and, at the last allowed call, wrongly deny it. step() therefore takes an authorizer, and the adapter is phase-aware.
2. run() swallows any Exception from a hand, so a NullHand that raised an ordinary exception would have been recorded as a failed call and the run would have gone on. HarnessModeViolation is a BaseException.
3. Replaying an unanswered tool call forever would deadlock a session after a gate or after the hook burned the call. Stale calls are now dropped and told to the model as failures.
4. A tool result for a call the hook never authorized is not fatal. It is logged as `ungoverned_result_reported`, not trusted, and fed back as a failure.
5. GovernedKernel refuses absolute and drive paths, so real harness paths will be denied until an adapter maps them. Open blocker for live use.

Not built: core mode, real token streaming, the hook transport, the supervisor, any live DSH evidence (checkpoint 10). Status PARTIAL.

## Checkpoint 4 follow-up: a kernel-only PASS could still write verified learning (fixed)

ChatGPT's review of the checkpoint 4 commit found that GovernedCore.step() finished through the same `_finish` as run(), so a kernel-only PASS wrote a lesson to memory even though the slot reported it as PARTIAL. Confirmed in the code (governed.py, the memory_write branch of `_finish`). Fixed with a flag, `learn_needs_adjudication`, that only step() sets: a kernel-only PASS now logs `memory_write ok=false` and writes nothing; a PASS confirmed by an independent adjudicator writes as before; a PARTIAL never writes. run() is byte-for-byte unchanged and still learns from a kernel-only PASS. That is legacy behaviour I did not change; it is an open owner decision (see the register). Tests: 5 new step tests, 2 new slot tests; three deliberate breakages of the new rule were all caught.

## Remaining plan (revised 4 Nov 2026 after the second ChatGPT review)

Items 1 to 4 are done. B1 to B10 replace old items 5 to 10. Every item carries the same completion requirement: commit, test, read back each file by blob SHA, run the full suite from a clean GitHub checkout, and log it here. Repository verification is not saved for the end.

| # | Item | Done when |
|---|---|---|
| B1 | Path mapping and hook decision core | Real harness paths map to what the kernel accepts; a pure decision function is default-deny; unknown tools denied; unavailable decisions deny; owner-only escalation. A written coverage table lists every tool route DSH has (native, Code Mode, MCP) and whether it reaches the decision, and anything that does not is listed as a gap |
| B2 | Hook transport | Loopback /hook with a bearer token in the contract format; real-socket tests; every refusal happens before a decision. Also the DSH-side forwarder plugin (a `tools/pre-execute` listener that fails closed, a synchronous guard over an approved set, and a `hook_attached` report), written and tested here against a mock of DSH's context. Loading it in the real DSH is B10 |
| B3 | Supervisor launch and ownership | Argument list, allowed environment, fixed directory, process group; pid, start time, executable and argument hash recorded; attaching is observe-only. Icarus reads back the model route and the forwarder configuration and claims control of a launched DSH only after the route points at the slot and `hook_attached` has arrived; otherwise it reports an uncovered boundary |
| B4 | Supervisor stop and evidence | Grace period, timeout, crash handling, whole-tree kill with proof it is gone, capped output in the ledger; Windows behaviour marked unproven |
| B5 | File snapshot check | Before/after hashes of scoped paths; UNEXPLAINED_CHANGE for changes no approved call explains; what it cannot see is stated |
| B6 | Fixture integration | Slot, hook and supervisor on one session against a stand-in harness. A component-integration fixture, not proof of pilot control |
| B7 | Mandatory adjudicator | Live mode refuses to start without an independent adjudicator; nothing is reported as PASS or learned without it |
| B8 | Resume after a crash | Replay the verified ledger to restore nonces, burned calls, gates, budgets and milestone; refuse a broken chain |
| B9 | Icarus pilot command layer (replaces close-out) | A fixture shows Icarus accepting an owner objective, creating the task, selecting a model through a provider-independent interface, creating the session and launching or configuring DSH, directing it through the slot and hook, then verifying independently and deciding to continue, stop or work a blocker. It also shows DSH cannot silently switch away and keep executing effects; anything that cannot be enforced is reported as a gap. The live-DSH acceptance script and instructions are written here |
| B10 | Live Icarus pilot acceptance inside DSH (strengthened) | Icarus starts first, selects a model, starts or commands the real DSH process, initiates a task, directs an authorized tool action and verifies its result; then the failure boundaries are tested on purpose: a denied action; Icarus stopped; the forwarder removed or disabled; alternative execution routes (another provider, Code Mode, shell, MCP); process termination. None may silently produce an unauthorized effect, and any exception is reported as an uncovered boundary. Only observed behaviour counts; DSH's own report is not verification. BLOCKED from this chat: it needs a session inside the laptop harness, and only Icarus awards PASS |

## Review of the revised plan (ChatGPT, 4 Nov 2026): REVISE THE PLAN, and how each point was handled

1. Items 1 to 8 stay as written. Item 6 is labelled a component-integration fixture, not proof of pilot control. Done.
2. Item 9 replaced by the Icarus pilot command layer. Agreed: the earlier plan could produce a model endpoint, a hook, a supervisor and a ledger and still leave Icarus unable to start a task and command DSH. Done (B9, contract section 9).
3. Item 10 strengthened to a whole-task live test with the failure boundaries. Agreed (B10). One addition from me: what DSH does when the slot or hook is unreachable is unknown and may fail open, so "Icarus unavailable" is a test that could fail, and the result goes in the register.
4. Repository close-out moves into every item. Agreed; it is now part of each item's completion requirement.
5. The kernel-only PASS learning write must be fixed before item 1. Agreed and done (section above).
6. Core mode and token streaming do not get their own items, and must not disappear. Agreed; they are in the register below.

## Unresolved-capabilities register

| Capability or question | Status | Where it lands |
|---|---|---|
| Core mode (slot answering in core mode, run() through the Session) | Not built; a core-mode session is refused with CORE_MODE_NOT_IMPLEMENTED | Only if a demonstrated DSH requirement needs it |
| Real token streaming | Not built; streaming replays a finished turn | Only if DSH needs real streaming (B10 will show) |
| Legacy run() learns from a kernel-only PASS | Unchanged on purpose; step() no longer does | Open owner decision |
| DSH accepts a plain http loopback base URL, streaming or not, tool calls through a custom provider, and the installed version | A custom provider with a base URL and `api: openai-completions` is documented; http loopback, streaming and tool calls are not stated | B10 |
| Hook transport and what DSH does when Icarus is unreachable | Grounded in the docs: a forwarder plugin (pre-execute listener plus guard) is the route; DSH's approval seam alone is not enough. An unanswered approval is denied, but that says nothing about a DSH that runs without the forwarder | B2 builds it, B10 tests it |
| Whether a pre-execute listener may await a network call, whether DSH's callId is the id the slot returned, whether the guard sees the proposed arguments, and whether Icarus could answer through the ACP bridge | Unverified | B10 |
| DSH-side forwarder plugin (JavaScript, runs inside DSH) | Not written; new scope in B2 | B2 |
| Real DSH launch command and arguments | Unknown | B3 fixture, B10 live |
| Windows process-tree termination | Unproven | B4 marks it, B10 proves it |
| Detection of execution outside the hook | Partial (file effects only) | B5, B10 |
| Real kernel refuses absolute and drive paths | Open blocker | B1 |
| Resume after a crash | Not built | B8 |
| Owner signing tool and key custody for decisions | Not built; custody cannot be proven by code | Before live use |
| Provider-independent model selection by Icarus | Not built | B9 |

## DSH interface verification (ChatGPT, 4 Nov 2026), checked against the same sources by me

Result: the three findings hold, with refinements that change the design of B2 and the tests of B3 and B10. No checkpoint redesign. Details are in CONTRACT.md sections 0, 4 and 6.

1. A localhost model endpoint is supported by DSH's custom-provider configuration. Not stated: plain http loopback, streaming, and tool calls through a custom provider. Untested against the installed DSH.
2. External approval is not as simple as the summary suggests. `approval/request` is a same-process event, fires only when a pre-execute decision is `ask`, and carries no tool arguments. It cannot carry the exact-argument binding, and an allowed call never reaches it. The usable route is a forwarder plugin using a `tools/pre-execute` listener (sees the arguments) plus a synchronous guard (final, cannot be reversed). That plugin is new work and is now part of B2.
3. "Icarus unavailable": an unanswered approval is denied, but only on the approval path. Our own forwarder fails closed on a timeout or an unreachable Icarus, and the guard denies anything not approved. A DSH started without the forwarder has only its own policy. B3 must verify the configuration before claiming control, and B10 must test the forwarder being absent.
4. The review says the checkpoint 4 internal-PASS issue is unresolved. That predates commit 73a1858d, which fixed it in step(); legacy run() still learns from a kernel-only PASS and is listed in the register as an owner decision.
5. Scope growth to confirm: the DSH-side plugin is JavaScript, so B2 now includes writing and mock-testing it here. It cannot be run against a real DSH from this chat.
