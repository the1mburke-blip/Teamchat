# T1 — ICARUS FINAL FULL-PREFLIGHT ATTEMPT

Purpose: reusable final-attempt template for integrated agent/app debugging after multiple partial fixes. Use only after canonical history/training retrieval and current-local-source inspection.

## Governing rules
- MEASURE TWICE. CUT ONCE.
- NO EVIDENCE = NO CLAIM.
- NO SERIAL PATCHING.
- NO SECOND REPAIR.
- NO SECOND BUILD.
- NO GEMINI CALLS when Gemini is an identified external blocker.
- Freeze already-passed layers; reopen only on genuinely new evidence.

## Current-state declaration
Before any mutation, list all PASS/CLOSED layers explicitly. For the 2026-09-24 Icarus case these included:
- Temurin JDK 17
- Gradle 9.3.1 direct execution
- AGP/Kotlin compatibility
- native-platform.dll
- missing gradlew/gradlew.bat not a blocker
- Kotlin compile baseline
- APK build/install
- launcher resolution
- objective field population
- sendMessage invocation
- task creation/task ID
- Composio transport
- required Accept headers
- JSON/SSE support
- inputSchema contract
- x-consumer-api-key path
- GitHub read-only execution
- destructive/downstream governance
- zero-call destructive harness
- redirect_url contract
- response.session.id -> request.session_id contract
- Gemini-bypass test entrypoint
- bypass build/install
- bypass SEARCH_TOOLS runtime

## Known external blocker
If Gemini is HTTP 429/quota-limited, mark it as external and do not call Gemini in this test.

## Phase 1 — full preflight before mutation
Use CURRENT LOCAL SOURCE as authority. Trace the complete runtime path end to end before editing:

test-only post-Gemini entrypoint
-> task creation
-> governance
-> SEARCH_TOOLS
-> SEARCH_TOOLS response parsing
-> toolkit extraction
-> connection-status extraction
-> session extraction
-> connectionRequiresAuthentication(...)
-> PENDING_AUTH persistence
-> MANAGE_CONNECTIONS
-> redirect_url parsing
-> auth UI rendering

Inspect every relevant current-local function/call site.

Build a blocker matrix covering:

A. SEARCH_TOOLS response shape
- exact location of toolkit_connection_statuses
- exact field names
- has_active_connection representation/type
- status/status_message representation
- accounts representation/count

B. Connection gate
- exact predicate used by connectionRequiresAuthentication
- every accepted unauthenticated representation
- whether logic wrongly depends on one hard-coded status string
- whether toolkit variants are handled generically

C. Session
- exact parsed nesting for response.session.id
- extractor handles actual JSON-RPC/SSE wrapper
- no fabricated/generated fallback session IDs
- session survives into TaskState/PENDING_AUTH
- same value supplied as MANAGE_CONNECTIONS session_id

D. MANAGE_CONNECTIONS request
- correct meta-tool name
- action=add
- exact toolkit slug from SEARCH_TOOLS
- same session ID
- argument nesting matches actual schema

E. MANAGE_CONNECTIONS response
- wrapper mapped correctly
- redirect_url found at actual nesting level
- initiated status handled
- accounts/status fields cannot falsely fail the flow
- redirect URL safely exposed to UI

F. PENDING_AUTH state
- objective persisted
- toolkit persisted
- downstream tool persisted
- session ID persisted
- state becomes PENDING_AUTH/AUTH_REQUIRED
- no downstream execution before ACTIVE

G. UI
- auth URL visibly rendered/clickable
- AuthRequired outcome not discarded
- state survives recomposition/navigation as intended

H. Resume contract
Statically verify:
- connection can be rechecked after auth
- preserved objective can resume
- execution occurs only after ACTIVE

I. Genericity
No toolkit-specific production branching unless external schema proves unavoidable. Intended pattern:
objective -> SEARCH_TOOLS -> toolkit discovery -> connection state -> auth if required -> execute after ACTIVE.

J. Test-path integrity
Bypass path must reuse production task persistence, governance, Composio client, session handling and auth state. No parallel fake implementation.

## Phase 2 — predict next blockers before mutation
Explicitly inspect whether any of these would become the next blocker:
1. session.id extraction null
2. session extracted but not persisted
3. MANAGE_CONNECTIONS argument shape wrong
4. wrong toolkit slug selected
5. redirect_url parser misses nesting
6. AuthRequired generated but UI does not display URL
7. PENDING_AUTH objective/session/toolkit not persisted
8. initiated status misclassified
9. downstream execution attempted before ACTIVE
10. bypass diverges from production post-reasoning orchestration
11. compile/import/signature error in touched files
12. launcher/test invocation cannot trigger bypass hook

Do not wait for runtime to discover these one at a time.

## Phase 3 — one atomic repair
Only after the blocker matrix is complete, make ONE bounded correction covering every preflight-proven defect in the affected auth-handoff path.

Allowed only if proven necessary:
- SEARCH_TOOLS connection-status parsing
- connectionRequiresAuthentication predicate
- session extraction/persistence
- MANAGE_CONNECTIONS argument mapping
- redirect_url extraction
- PENDING_AUTH/UI surfacing

Do not touch unrelated passed layers.

## Phase 4 — static readback
Before build, prove:
- SEARCH_TOOLS_CONNECTION_FIELDS_PARSED: TRUE
- UNAUTHENTICATED_GATE_GENERIC: TRUE
- SESSION_ID_PATH_VALID: TRUE
- SESSION_PERSISTENCE_VALID: TRUE
- MANAGE_CONNECTIONS_ARGUMENTS_VALID: TRUE
- REDIRECT_URL_PATH_VALID: TRUE
- PENDING_AUTH_PERSISTENCE_VALID: TRUE
- AUTH_UI_PATH_VALID: TRUE
- NO_EXECUTION_BEFORE_ACTIVE: TRUE
- PRODUCTION_GEMINI_PATH_UNCHANGED: TRUE
- BYPASS_REUSES_PRODUCTION_ORCHESTRATION: TRUE

Also inspect all changed files for compile/import/signature defects before building.

## Phase 5 — one build
Use the already-verified toolchain. Run exactly one:
:app:assembleDebug --no-daemon

If build fails:
STOP.
Return complete compiler error set.
NO REPAIR.

## Phase 6 — one install
Install the new APK once on the verified device. No reinstall loop.

## Phase 7 — one runtime acceptance
Invoke the verified test-only Gemini-bypass entrypoint.

Expected:
task
-> governance
-> SEARCH_TOOLS
-> toolkit discovered
-> inactive connection recognized
-> session.id extracted
-> session persisted
-> MANAGE_CONNECTIONS action=add
-> redirect_url parsed
-> PENDING_AUTH
-> URL visible
-> STOP

PASS requires:
- GEMINI_CALLED: FALSE
- TASK_CREATED: PASS
- SEARCH_TOOLS_HTTP_RECEIVED: TRUE
- CONNECTION_STATE_CAPTURED: TRUE
- UNAUTHENTICATED_GATE: PASS
- SESSION_ID_EXTRACTED: TRUE
- SESSION_ID_PERSISTED: TRUE
- MANAGE_CONNECTIONS_CALLED: TRUE
- MANAGE_CONNECTIONS_ACTION: add
- SESSION_CONTINUITY: PASS
- REDIRECT_URL_PRESENT: TRUE
- AUTH_URL_VISIBLE: TRUE
- PENDING_OBJECTIVE_PRESERVED: TRUE
- PENDING_TOOLKIT_PRESERVED: TRUE
- PENDING_SESSION_PRESERVED: TRUE
- DOWNSTREAM_EXECUTION_BEFORE_AUTH: NOT_ATTEMPTED
- GENERIC_COMPOSIO_PATH: PASS
- FINAL_STATE: READY_FOR_OWNER_AUTH

## Hard stop
If ANY new blocker appears:
STOP IMMEDIATELY.
No repair again.
No rebuild again.
No reinstall again.
No retry again.
No Gemini call.
Do not reopen passed gates.

Return:
BLOCKED
FIRST_FAILING_LINK: [exact]
FULL_REMAINING_EVIDENCE: [complete relevant evidence]
PREDICTED_NEXT_BLOCKER: [exact or NONE IDENTIFIED]
ATOMIC_REPAIR_COUNT: [0 or 1]
BUILD_COUNT: [0 or 1]
INSTALL_COUNT: [0 or 1]
GEMINI_CALLED: FALSE
NO_SECOND_REPAIR: TRUE
NO_SECOND_BUILD: TRUE
NO_RETRY: TRUE

## Reusable lesson
Map the complete remaining contract and predicted failure surface before the final mutation. For late-stage integrated-agent debugging, the unit of planning is the full current-local execution path plus auth/session/governance/UI acceptance surface—not the first visible error.
