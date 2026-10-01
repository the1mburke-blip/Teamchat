# HV-EXP-075 — Icarus Harness DeepSeek session: evidence-first recovery, external-model discipline, and root-brain supervisor

- experience_id: HV-EXP-075
- date_utc: 2026-10-01
- source_agent: SOL / DeepSeek Harness
- task_problem: Advance Icarus toward autonomous primary-brain failover while preserving task state, avoiding duplicate mutations, and integrating external tools without wasting time on unsupported paths.
- failure_signature: Two major rabbit holes consumed owner time: (1) Composio/Harness MCP integration was debugged from inside Harness for too long before an outside-the-box direct PowerShell request proved HTTP 401 at Composio; (2) a DeepSeek build drifted into app.asar extraction and DSH runtime reverse engineering instead of extending the existing Icarus path.
- root_causes:
  1. Official + unofficial/prior-art search was not invoked early enough when an integration resisted.
  2. External DeepSeek models do not inherit Teamchat operating rules; task-specific preflight, stop conditions, and scope fences must be embedded directly in their prompts.
  3. Earlier router evidence was accepted too readily; later audit proved the existing router execution/trace was simulated and one model ID was a placeholder.
  4. Model/provider failures were initially treated too close to task failures rather than recoverable brain failures.
- successful_recovery:
  - Recovery audit isolated all off-lane ASAR artifacts and preserved the legitimate Icarus workspace.
  - Built icarus/runtime/checkpoint.py with atomic writes, task IDs, monotonic checkpoint sequence, verified/pending steps, provider quarantine, mutation ledger, idempotency keys, and OUTCOME_UNKNOWN reconciliation.
  - Checkpoint/idempotency suite passed 19/19 including crash/reload, duplicate replay prevention, conflicting payload detection, and reconciliation-before-retry.
  - Verified Harness root-agent creation contract: ctx.agents.create(...) can create a fresh top-level/root agent when parentAgent is omitted.
  - Built and registered profile plugin icarus-supervisor. HMR loaded it live; tool icarus_supervisor_spawn appeared.
  - Smoke test created fresh ROOT session session-845abf3a4aba40fc, preserved task_id 0e417d8e-3002-4384-bf05-439b282990ce, kept parentAgent absent, and prevented duplicate creation on repeated invocation.
  - Live provider inventory found one currently usable route: deepseek-account / deepseek-flash. OpenRouter route exists but credential was absent; Google route had no declared model/credential.
  - Direct PowerShell MCP initialize to https://connect.composio.dev/mcp using the configured ck_* consumer key returned HTTP 401 Unauthorized, proving the remaining Composio blocker is reproducible outside Harness.
- verification_evidence:
  - DeepSeek final supervisor report: plugin loaded, ROOT_AGENT_CREATED=YES, PARENT_AGENT=ABSENT, duplicate_prevented=true on second call, checkpoint SHA unchanged.
  - 19/19 checkpoint tests PASS.
  - Recovery audit: previous router runtime execution was mocked; trace not valid as live provider-switch evidence.
  - Composio external test: HTTP_STATUS 401 / Unauthorized from direct PowerShell call.
- what_not_to_retry:
  - Do not return to app.asar extraction or build a parallel DSH runtime for Icarus failover.
  - Do not claim automatic A→B model failover until a second live route exists and a real cross-model acceptance test passes.
  - Do not spend another long Composio session without first doing official + unofficial prior-art research and a direct outside-Harness test.
  - Do not assume an external model knows Teamchat immutable rules; encode a short task-specific preflight, blockers, stop conditions, and PASS evidence in the prompt.
  - Do not kill a Harness process without first identifying which session/run is active and what state is already persisted.
  - Do not accept model self-report or simulated trace as runtime evidence.
- next_valid_moves:
  1. Restore/verify a second live provider/model route.
  2. Run real acceptance: Brain A fails -> Icarus supervisor creates Brain B root session -> same task/checkpoint continues -> no duplicate mutation -> task completes.
  3. Give Composio one bounded 20–30 minute spike only after deep prior-art sweep; if direct fresh ck_* test remains 401, park local debugging and use support/alternate integration.
- reusable_principles:
  - **Search from both directions early: official implementation contract + unofficial/community failures/workarounds before serial repair.**
  - **A model failure is not a task failure. Persist the task above the model session and continue on another root brain.**
  - **External executors require their operating boundaries in the prompt; they do not inherit Teamchat discipline automatically.**
  - **When a run drifts, audit and preserve persisted progress before issuing any destructive stop/cleanup action.**
  - **Evidence hierarchy: physical runtime state > trace produced by real runtime > config presence > model self-report/simulation.**
- cost_note: DeepSeek account-backed Harness usage was confirmed to consume CNY balance; observed spend was small, but monetary cost is not zero and must be disclosed in future preflights.
- confidence: HIGH
