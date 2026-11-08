# ICARUS-REPO-CONSOLIDATION-AUDIT — preflight

[TIMESTAMP] 2026-11-08T21:54:21Z
[FROM] [CODEX]
[TO] [OWNER]
[STATUS] PREFLIGHT
[ACTIVE_OWNER] CODEX
[OWNER_AUTHORITY] Michael's directive in the active conversation authorizes local refactor, tests, branch/PR creation; monetary ceiling €0. No merge, paid provider, secret, deployment, or production-runtime action requested.
[OBJECTIVE] Audit Teamchat's active Icarus package/consumers; consolidate runtime, snapshot, and harness implementations beneath `icarus/`; update imports/workflows/tests; run required local checks; open a PR against main.
[REPOSITORY] the1mburke-blip/Teamchat
[BASE] main `1f0a35eeb1b99395632416233392f7794c7375b5` (PR #173 squash merge)
[BRANCH] `refactor/icarus-consolidation`; remote branch created from that base. Failure records are now committed/read back on the branch through GitHub; latest verified record commit is `70bfed84a0fcd25af7b1e3955f7af8d5e562175b`. A separate preflight-only commit must be read back before source edits/tests.
[DUPLICATE_CHECK] GitHub issue search for exact task ID: no open result. Open PR search for “icarus consolidation”: no result.
[HISTORY_REVIEW] Read Teamchat OPERATING_RULES.md, HANDOFF_PROTOCOL.md, MICHAEL_USER_GOVERNANCE.md; latest CHAT_LOG.md and TRAINING_MATRIX.md entries; 2026-11-07 ICARUS Genesis retrospective; relevant runtime records/memory. HV-EXP-124 records the same preflight-ordering failure; HV-EXP-153 says source/CI receipts are partial proof and protected-branch work must use PR checks. This turn's initial run also failed Rule 39 and was captured as HV-EXP-154 before retry.
[TRAINING_REVIEW] PASS. HV-EXP-124, verbatim: “For a canonical audit mutation, first commit a bounded preflight-only receipt (training quote, known failures, ownership, route, costs, exact target and 12-rule review), read it back, then perform substantive documentation writes.” Relevance: this refactor must have a durable, verified route/cost/rule record before source changes or tests.
[KNOWN_FAILURES] 1) Initial worktree creation preceded preflight; process FAIL, recorded as HV-EXP-154 and CHAT_LOG. 2) Local Git commit failed first for missing author, then twice with MSYS sh.exe NtCreateDirectoryObject permission error even with auto-GC/signing disabled; no commit was created. 3) First connector persistence attempt failed before write because TextDecoder is unavailable; switched to connector UTF-8 read/write, successfully committed and read back failure records. Do not retry those local commit/base64 routes unchanged. 4) PR #173 previously needed updated base/checks before merge; preserve branch protection and verify required checks on this PR. 5) Athena.gs is referenced by a test and GAS workflow documentation; do not remove as “dead.”
[CURRENT_STATE] Local worktree is `C:\Users\the1m\Documents\Codex\teamchat-icarus-consolidation`, local branch at original base with two local governance files dirty; source files remain unchanged. Remote branch has the two failure-record commits. Python 3.12, Docker CLI, and Node are present; Docker daemon availability is not yet verified. GitHub connector can read/write repo files/branches. Local Git commit is currently blocked; for durable commits use GitHub connector tree/commit/ref route or contents API, not repeated local commit. No tests have run yet.
[PRIOR_ART_AND_CONSUMERS] At base, runtime is `icarus/runtime/icarus_run.py` with `icarus/runtime/{approved-routes.json,endpoints.json,enforcement.json}`. Known consumers include `.github/workflows/icarus-pulse.yml`, `.github/workflows/icarus-runtime.yml`, `.github/workflows/teamchat-router.yml`, runtime tests and denied-path checks. Pulse also calls `scripts/icarus_duty_runner.py`. Snapshot implementation `scripts/update_prime_snapshot.py` is invoked by `prime-snapshot-sync.yml` and imported by `tests/test_update_prime_snapshot.py`. `harness_runner.py` invokes the Docker test image; `harness-runner.py` is a separate deterministic evidence CLI called by `icarus-harness-gate.yml` and multiple tests/CODEOWNERS. Keep their distinct roles clear. Memory under `icarus/memory/` must be preserved. `icarus/athena-gas/Athena.gs` plus its test/deploy workflow is an independently used GAS path and is out of removal scope. Experimental/ghost workflows target separate drafts; classify each before proposing deletion. On PR, repository search found only `icarus-harness-gate.yml` listens for `pull_request`; its two required jobs are `harness` and `completion-integrity`. No model/provider call was found on that PR route.
[PLANNED_ROUTE] Complete a reference/import/path audit, then migrate implementations into `icarus/core/` and `icarus/harness/`. Update all in-repo imports, tests, and workflow module invocations. Retain narrow compatibility entry points if a call surface is not fully controlled or a contract requires the old path; do not remove data/config/memory or experimental files without proof of no consumer. Review path-root calculations, denied-write paths, package imports, Docker context, and workflow working directories. Required local execution: `python harness_runner.py` and completion-integrity (`python harness-runner.py --audit-state-writes`, plus local-equivalent test suite as needed). Open PR; do not merge.
[PASS_EVIDENCE] Complete audit/reference map and change summary; local harness and completion-integrity outputs with exit codes; package/workflow diff; PR URL and branch HEAD SHA; GitHub status-check readback on that head. Unrun checks or missing runtime/process evidence must be reported as such.
[COST] €0 incremental external spend. No paid API/model calls, credentials, installation, or deployment. Pull-request workflow is public-repo CI with two required jobs and no provider call. Tool/token allowance is unmetered by available telemetry; bound the fresh implementation stage to at most 40 GitHub connector operations and 30 shell operations, then stop and re-preflight if exceeded. One owner task; no delegation. Owner time estimated 10–20 minutes review; execution estimate 45–90 minutes.
[BLOCKER] Stop at any source/import/path issue that cannot be resolved without changing runtime authority, credentials/provider configuration, external deployment, or required protected checks. Do not weaken gates. If GitHub API branch/commit route fails, diagnose evidence before a materially different retry. Any material scope/tool/cost change requires re-preflight.
[PREMATURE_MUTATION] The local worktree was created before this preflight: process FAIL is preserved as HV-EXP-154; this receipt does not cure it. The fresh run starts only after failure-record readback and this receipt's own commit/readback.
[STATUS] READY for isolated source audit/refactor only after this preflight file is committed and physically read back. The initial attempt remains PROCESS FAIL; overall governance closure requires a separate post-task tracker.

## Twelve immutable rules — contextual application

1. **R1 PRIOR ART FIRST** — inspect existing package, call sites, tests, denied paths, runtime config and prior refactor history; preserve working contracts and don't invent another runtime.
2. **R2 PREFLIGHT FIRST** — this receipt must be committed/read back before edits or tests.
3. **R3 CORRECT ROUTING** — use local source/test tools for code; GitHub connector for remote branch/PR/check readback; no simulated delegation or fabricated execution.
4. **R4 HISTORY/TRAINING FIRST** — apply HV-EXP-124, HV-EXP-153, HV-EXP-154 and the genesis retrospective before execution.
5. **R5 NO EVIDENCE = NO CLAIM** — classify files dead only after searching every workflow/import/test/config; claim PASS only from command/check outputs.
6. **R6 €0 / SPEND DISCIPLINE** — no paid providers, billing/secret changes, installs, or deployments.
7. **R7 ALLOWANCE DISCIPLINE** — use stated bounded tool-call budgets; record unknown model tokens as unmetered, not zero.
8. **R8 NO BLIND RETRIES** — do not repeat failed Git commit/base64 routes; diagnose an exact failure before any alternate attempt.
9. **R9 WORK THE BLOCKER** — resolve the local commit limitation through the authorized GitHub route while continuing read-only code audit; don't bypass branch protection.
10. **R10 MATERIAL CHANGE = RE-PREFLIGHT** — stop and replace this receipt if route, scope, cost, owner, capability, or target changes.
11. **R11 STARTED != COMPLETED / PASS REQUIRES EVIDENCE** — the local tests and two remote required checks need independent readback; opening a PR is not merge/completion.
12. **R12 LEARNING MUST BE LOGGED** — record verified outcome/failures and read back; create separate post-task compliance tracker before governance closure.


## Audit addendum — gate path condition checked (2026-11-08T21:54Z)

Direct read of `dsh/state_write_gate.py` confirms `protected(path)` returns false for `.github/`, `docs/`, `tests/`, and for code files that are not named state/status/ledger/goal files; the trusted-file list is consulted only inside `verify_receipt()`, which runs when the PR changes protected state. The planned package/runtime/snapshot/harness source, tests and workflow changes do not add or alter protected state artifacts. Therefore the current completion-integrity route can accept this refactor without a receipt, while still checking ordinary source changes. I will add the relocated harness implementation to `TRUSTED_FILES`, keep compatibility entry points until all consumers move, and verify the no-protected-state condition in the final diff. This corrects the initially considered gate concern; no scope or cost change.

## Expanded source consumer evidence

- Runtime has direct workflow consumers in `icarus-pulse.yml`, `icarus-runtime.yml`, and `teamchat-router.yml`; pulse calls the separate duty runner. Runtime tests import the old module, and enforcement contains old deny-path names. Runtime configuration JSON can stay at its current data location unless path audit demonstrates a need to move it.
- Snapshot has one workflow invocation and one direct test import; its repository root calculation depends on `__file__` depth.
- The two root harness scripts are both trusted by `dsh/state_write_gate.py`, copied or run by Docker/CI, and imported/executed by tests. Keep thin root shims, preserve their CLI contracts, move implementations into package modules, add the implementation path to the trusted list, and update the workflow/test entry points.
- Athena GAS is retained because `test-athena.js` loads it, the deploy workflow targets it, and `icarus-runtime.yml` documents the mutually exclusive runtime route. No legacy/dead removal is justified from current evidence.
- Ghost/experimental workflows operate on separate draft paths; they are not direct consumers of files being moved. No deletion is authorized by this audit.

[UPDATED_ROUTE] Continue the authorized code-only refactor as scoped; no protected governance/runtime state files will be edited. If testing requires a config/state mutation or tests trigger provider access, stop and re-preflight.


## Re-preflight after local Docker blocker (2026-11-08T21:54Z)

Material verification-route update under R10: `docker image inspect teamchat-harness:test` exited 1 because the Docker Desktop Linux engine pipe was absent. The exact failure was recorded and read back as HV-EXP-155 before changing route. Do not start or install Docker. Local Docker harness status is BLOCKED; run the directly executable Python suite against the edited worktree as the local substitute. The PR's `harness` job must independently build `teamchat-harness:test` from the PR head and run the container harness. The `completion-integrity` job must run on the same head. Report these outcomes separately.

### R1–R12 re-review for the changed verification route
1. **R1 PRIOR ART FIRST** — no source architecture change; known Docker wrapper contract and PR gate retained.
2. **R2 PREFLIGHT FIRST** — HV-EXP-155 was recorded/read back; this replacement receipt is read back before direct tests.
3. **R3 CORRECT ROUTING** — direct Python suite runs locally; Docker image harness runs only in PR Actions where the runner can build it.
4. **R4 HISTORY/TRAINING FIRST** — apply HV-EXP-124, HV-EXP-153, HV-EXP-154 and new HV-EXP-155.
5. **R5 NO EVIDENCE = NO CLAIM** — local Python tests cannot be described as Docker harness pass; wait for separate CI readback.
6. **R6 €0 / SPEND DISCIPLINE** — no daemon startup, installation, provider, secret, or paid API.
7. **R7 ALLOWANCE DISCIPLINE** — remain within the previously bounded request/shell caps; unknown token usage remains unmetered.
8. **R8 NO BLIND RETRIES** — the unavailable Docker pipe is not retried unchanged; the local route materially changes to Python tests.
9. **R9 WORK THE BLOCKER** — complete independent source/tests work, then use the authorized public-repository Actions path for container verification.
10. **R10 MATERIAL CHANGE = RE-PREFLIGHT** — this addendum captures the route change; any further change triggers another review.
11. **R11 STARTED != COMPLETED / PASS REQUIRES EVIDENCE** — local suite and both PR checks need actual exit/conclusion evidence.
12. **R12 LEARNING MUST BE LOGGED** — HV-EXP-155 is durable and read back; log final outcomes separately.

[UPDATED_LOCAL_ROUTE] Run `python -m pytest` on the bounded affected suites (or full suite if available); do not claim the Docker-backed `harness` job locally passed. The PR gate remains mandatory.


## Re-preflight after pytest temp-root failure (2026-11-08T22:10Z)

The direct Python test attempt and exact aggregate result were durably logged/read back as HV-EXP-156 before retry. It exited 1 with 42 failed, 28 passed, 46 errors and 19 passed subtests. The captured stack shows repeated WinError 5 during TemporaryDirectory cleanup under the sandbox's AppData Temp path; because the tool truncated output, other test causes are unknown. No test was repeated. Next materially different route: use a workspace-local writable temp directory by setting both `TMP` and `TEMP`, run the affected suite once, capture full output to a workspace log, and classify the first remaining failures. Do not claim a code regression or PASS from the first run. Docker harness stays BLOCKED until a PR runner builds/runs its image.

### R1–R12 re-review for the revised local test route
1. **R1 PRIOR ART FIRST** — the test command and Windows temp constraints are now included in prior art; no neighboring route substitution.
2. **R2 PREFLIGHT FIRST** — log/training failure receipt HV-EXP-156 has been read back; this re-preflight is read back before retry.
3. **R3 CORRECT ROUTING** — local pytest with workspace temp is a diagnostic route; Actions remains authoritative for the container harness and PR integrity gate.
4. **R4 HISTORY/TRAINING FIRST** — apply HV-EXP-124 and HV-EXP-153–156; the new temp failure is explicitly surfaced.
5. **R5 NO EVIDENCE = NO CLAIM** — first suite result is environment-tainted; classify only full exact output after the changed temp route.
6. **R6 €0 / SPEND DISCIPLINE** — set environment variables only for the process; no daemon, paid service, installation, or provider call.
7. **R7 ALLOWANCE DISCIPLINE** — stay within remaining tool budgets; token use is unmetered.
8. **R8 NO BLIND RETRIES** — only retry after changing the temp root and retaining full output.
9. **R9 WORK THE BLOCKER** — finish diagnosis by isolating temp-path errors from true source failures; CI will test Linux packaging.
10. **R10 MATERIAL CHANGE = RE-PREFLIGHT** — this addendum records the route change; re-preflight again if the new evidence changes target or environment.
11. **R11 STARTED != COMPLETED / PASS REQUIRES EVIDENCE** — require command exit/status and subsequent CI result separately.
12. **R12 LEARNING MUST BE LOGGED** — HV-EXP-156 is recorded; append additional verified causes before any further retry.

[UPDATED_LOCAL_TEST] Use one affected-suite run with `TMP` and `TEMP` pointed to a writable directory under this repository, preserving full output to an allowed workspace file. Do not rerun the Docker harness or the prior command unchanged.


## Re-preflight after core-path protection regression (2026-11-08T22:13Z)

HV-EXP-157 records the affected-suite result before repair: 86 passed, 2 failed. Read-only inspection found `dsh/cordis/kernel.py:HARD_DENY` contains `icarus/runtime` but no `icarus/core`; `validate_path` already compares deny prefixes case-insensitively. The next code change adds `icarus/core` to this existing protected set and keeps both canonical and case-variant regression tests. The test run will be repeated once with the workspace temp root and complete output retained. No auth, runtime, provider, or deployment scope changes.

### R1–R12 review for this repair
1. **R1 PRIOR ART FIRST** — reuse the existing case-insensitive `HARD_DENY` mechanism; add no parallel policy.
2. **R2 PREFLIGHT FIRST** — HV-EXP-157 is read back; this scoped repair receipt is read back before editing.
3. **R3 CORRECT ROUTING** — edit local policy/test files; use GitHub only for branch commits and PR evidence.
4. **R4 HISTORY/TRAINING FIRST** — apply HV-EXP-157 and prior HV-EXP-124/153/154/155.
5. **R5 NO EVIDENCE = NO CLAIM** — current test proves only the two path checks fail; rerun required after repair.
6. **R6 €0 / SPEND DISCIPLINE** — no paid service or provider call; no Docker startup.
7. **R7 ALLOWANCE DISCIPLINE** — stay within remaining bounded shell/connector budget; tokens remain unmetered.
8. **R8 NO BLIND RETRIES** — change the missing canonical deny prefix, then run focused tests before the full suite.
9. **R9 WORK THE BLOCKER** — repair DSH's own path policy, preserving denied access through all runtime layers.
10. **R10 MATERIAL CHANGE = RE-PREFLIGHT** — no route/scope/cost change; this addendum records the evidence and exact repair.
11. **R11 STARTED != COMPLETED / PASS REQUIRES EVIDENCE** — only focused and suite outputs can establish the fix.
12. **R12 LEARNING MUST BE LOGGED** — HV-EXP-157 captured the regression; record any further failure before retry.

[UPDATED_REPAIR] Add `icarus/core` to `dsh.cordis.kernel.HARD_DENY`; run only the two targeted deny-path tests once, then the affected suite once. Preserve output. CI remains the Docker verification surface.


## Owner-authorized local Docker harness route (2026-11-08T22:13Z)

Michael explicitly directed: “Ensure the updated trusted-file list passes the harness locally before opening the PR against `main`.” This supersedes the earlier local-route limit that avoided starting Docker. Start the already installed Docker Desktop engine solely to run the requested local harness. No install, config/credential edit, external provider call, or paid service is authorized. If Docker startup prompts for policy approval, licensing/payment, or configuration change, stop and report it. First attempt should use the existing local image; build from the repository Dockerfile only if needed and if it has no monetary spend. €0 remains binding.

### R1–R12 re-review for the owner-directed service start
1. **R1 PRIOR ART FIRST** — use the repository's existing Docker harness and Dockerfile.
2. **R2 PREFLIGHT FIRST** — this owner instruction and replacement preflight are recorded/read back before starting Docker.
3. **R3 CORRECT ROUTING** — local engine executes the requested harness; GitHub Actions remains independent post-PR evidence.
4. **R4 HISTORY/TRAINING FIRST** — apply HV-EXP-124 and HV-EXP-153–157; Docker was previously absent, so start the installed engine once.
5. **R5 NO EVIDENCE = NO CLAIM** — service started is not harness PASS; report actual command result separately.
6. **R6 €0 / SPEND DISCIPLINE** — no paid services or provider; stop on any paid prompt; no installation/config mutation.
7. **R7 ALLOWANCE DISCIPLINE** — no provider tokens; local Docker resource use is unmetered, no extra API route.
8. **R8 NO BLIND RETRIES** — after start, inspect engine/image; build only if missing; don't repeat an identical failure.
9. **R9 WORK THE BLOCKER** — the user-authorized local engine start resolves the named harness prerequisite within scope.
10. **R10 MATERIAL CHANGE = RE-PREFLIGHT** — this addendum records the authorization and exact limits; stop/re-review if broader action is needed.
11. **R11 STARTED != COMPLETED / PASS REQUIRES EVIDENCE** — only the full harness output establishes local PASS.
12. **R12 LEARNING MUST BE LOGGED** — record and read back any startup/build/harness failure before retry.

[UPDATED_DOCKER_ROUTE] Start the existing engine, inspect local image availability, then run the updated harness. No install or system configuration change.
