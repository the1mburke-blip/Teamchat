# Rules map: owner's immutable rules and SOP -> code -> test

Status: PARTIAL. Built alongside M1 in `icarus/agent/governed.py`; no existing file was changed.
Source of the rules: the owner's saved operating preferences (immutable rules, canonical SOP). Nothing here is Icarus-adjudicated yet.
Legend: ENFORCED = code refuses/records it and a test fails if it is removed (mutation-checked). NOT CODE = cannot be enforced inside Core; stated honestly.

| # | Rule / SOP clause | Status | Where | Test |
|---|---|---|---|---|
| 1 | NO EVIDENCE = NO CLAIM (never claim PASS/sent/done without evidence) | ENFORCED | `GovernedCore._finish`: PASS only if every declared item is verified by the kernel; worker claim is stored as "unverified" | test_pass_only_from_declared_evidence..., test_worker_cannot_pick_easier_evidence, test_worker_lie_downgrades_a_pass |
| 2 | PREFLIGHT FIRST (endpoint, token cost, money cost, owner, effort, PASS evidence, blockers, exact target) | ENFORCED | `Preflight` + `validate_preflight`; no model call until valid | test_requires_a_preflight_object, test_missing_preflight_fields_block_before_any_model_call |
| 3 | Exact target via live readback | PARTIAL | `target_path` is read back and hashed into `sources_read` and the log. A target that is not a repo file (channel, timestamp) is recorded as stated, not read back | test_sources_read_and_target_readback_are_reported |
| 4 | Material change in route/executor/cost/scope -> stop and re-preflight | ENFORCED | `fingerprint()` checked before and after every model call (includes the reasoner's current route, so failover counts) | test_route_change_mid_run..., test_executor_swap_mid_run... |
| 5 | SPEND: default EUR 0; no paid anything without explicit owner authorization | ENFORCED | `monetary_cost>0`, or a reasoner/hand with `paid=True`, needs `authority_ref`. Caveat: existing `OpenAICompatReasoner` has no `paid` flag yet, so a paid endpoint is not detected until it declares one | test_spend_needs_owner_authority, test_paid_reasoner_blocked_without_authority |
| 6 | NEVER SIMULATE AGENTS (never invent what another agent/tool said) | ENFORCED (structural) | Core never writes a model's or tool's output itself; `proposed_by` / `executed_by` come from the objects that ran; tool results enter history only from `hand.execute` | test_attribution_and_report_format |
| 7 | NO BLIND RETRIES | ENFORCED | an identical (tool,args) call that already failed or was denied is refused and never reaches the hand | test_blind_retry_is_refused..., test_hand_failure_is_a_blocker_and_not_retried_blindly |
| 8 | WORK THE BLOCKER; stop only for unresolved blocker, owner-only boundary, or second blocker | ENFORCED | first blocker -> told to investigate/route around; a success clears it; a second distinct unresolved blocker -> BLOCKED | test_first_blocker_is_worked..., test_resolved_blocker_does_not_count..., test_second_distinct_unresolved_blocker_stops |
| 9 | Escalate to owner only for auth, credentials, legal, payment, security, safety | ENFORCED | `OWNER_ONLY`; other escalations are refused with "work the blocker"; valid ones return BLOCKED with `owner_action` | test_owner_only_escalation_is_honoured, test_non_owner_escalation_is_refused... |
| 10 | PROTECT PRODUCTION: no mutation without authority + preflight | ENFORCED | any grant containing a write tool needs `authority_ref`; protected paths still denied by the M1 kernel | test_mutation_needs_authority |
| 11 | PROTECT CREDENTIALS; never expose secrets | ENFORCED (pattern-based) | secret paths denied (M1 kernel); `redact()` on prompts, history, decision log, reports. Pattern list is finite: an unusual secret format is not caught | test_secrets_never_reach_prompt_or_log, test_secret_in_write_args_is_not_logged, test_redact_patterns |
| 12 | STARTED != COMPLETED (assigned/queued/sent/attempted are intermediate) | ENFORCED | `Result.attempted` is separate from `Result.proven`; `completed` is true only for PASS | test_started_is_not_completed |
| 13 | Statuses: PASS (physically verified), PARTIAL (what is proven/unproven), BLOCKED (blocker + evidence) | ENFORCED | `Result.status`, `proven`, `unproven`, `reasons`; decision log is hash-chained | test_pass_when_every_declared_item_verified, test_log_chain_valid_after_a_governed_run |
| 14 | Verification independent of self-certification | PARTIAL | the kernel checks evidence itself, and the model never sees a way to set a status. An optional `adjudicator` callable can be required to agree (`kernel+adjudicator`). Without one, "independent" means independent of the model, not of Icarus | test_independent_adjudicator_must_agree |
| 15 | Every report states who proposed, who executed, when | ENFORCED | `Result.proposed_by/executed_by/adjudicated_by/at` and `report()` | test_attribution_and_report_format |
| 16 | State which logs/sources were read; if a required one was not read, say so and STOP | ENFORCED | `required_sources` must exist before any model call; read sources are listed with short hashes | test_required_source_missing_blocks_and_is_named, test_sources_read_and_target_readback_are_reported |
| 17 | RESULT first, PASS/PARTIAL/BLOCKED, evidence, cost, owner action | ENFORCED | `Result.report()` | test_attribution_and_report_format |
| 18 | Route every task to the correct agent; never absorb another agent's work; if you cannot delegate, say so and STOP | PARTIAL | optional `routes` {task kind -> executor name}; a mismatch or an unmapped kind -> BLOCKED "cannot delegate: STOP". No routing table ships yet (see open decision) | test_routing_fails_closed... |
| 19 | Default route is Core itself (user query -> verified solution -> user) | NOT CODE | architecture, see DESIGN.md | n/a |
| 20 | Reuse existing authenticated capabilities; route around defective wrappers | NOT CODE | needs the harness adapters (M2/M3) | n/a |
| 21 | Log reusable lessons | ENFORCED | lesson written only on PASS and only with an `Evidence:` line (M1 `Memory.write_back`) | test_lesson_written_only_on_pass |
| 22 | Do not expose routine breadcrumbs to the user | NOT CODE | reporting/UI behaviour for the app and daemon (M4) | n/a |

## Open decision (one question, not blocking)

Clause 18 names Saul (orchestrator/publishing), Claude (review/logic), Gemini (Google Workspace), DeepSeek (bulk drafts/data). With Icarus as the outermost agent those become executors under him, not peers above him. Proposed routing table, to be confirmed or edited by the owner before it is loaded:

- google_workspace -> gemini
- bulk_draft, data_transform -> deepseek
- publish -> the publishing executor (Buffer)
- code_review, long_reasoning -> claude

Until confirmed, `routes` is empty and routing is not enforced.

## Not yet proven

No live model call, no real harness adapter, nothing run on the owner's laptop, no Icarus adjudication. Statuses above are from offline tests (44 passing) and 17 deliberate code breakages, each caught by at least one test.
