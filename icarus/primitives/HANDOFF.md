# HANDOFF — icarus/primitives → daemon executor (for Claude Code on the laptop)

Proposed by: Claude (chat session, 2026-11-17 ~21:45 Europe/Dublin). Executor: Claude Code (laptop).
Owner approval: Michael, 2026-11-17 21:42 ("Anything that needs to be done to make this work in the
next 15 minutes, Claude Code can do it"). Apply the Teamchat rules, preflight and
`training/TASK_DELEGATION_TEMPLATE.json` as always. Self-verified work = PARTIAL, never PASS.

## Context (verified by reading the repo at main a784eed)
- Pulse = `icarus/athena-gas/Athena.gs` (Apps Script). Intake + model + gates + issue receipts. Cannot run code.
- Daemon = `Dockerfile` stage `icarus-daemon` → `proxy_monitor.py`. It ONLY logs detected
  `ICARUS_RUN` directives; it executes nothing. This is the gap.
- Verifier already exists: `icarus/harness/runner.py` (evidence gate; packet keys incl. task_id,
  decision_changing, owner_preauthorized, cost_tier, command, readback{file_hash|ledger_row};
  exit 0 verified / 1 fail / 2 invalid / 3 blocker).
- Branch `agent/icarus-primitives` (commit 8f93c6e) adds `icarus/primitives/` + `tests/test_primitives.py`,
  25 tests passing. Its SQLite lease lock is single-host only and `verify.py` duplicates the gate.

## Scope for this 15-minute session (branch `agent/icarus-primitives` only)
1. `icarus/primitives/gitledger.py` (new): ledger in the repo at `icarus/ledger/`
   - `queue/<job_id>.json` = filled template + `verify_spec`/readback, written at enqueue by the author.
   - claim = commit `claims/<job_id>.json` {runner, lease_expires} and `git push`; a rejected push
     (non-fast-forward) means the claim was lost → fetch, re-read, do not retry the same job blindly.
   - receipts appended to `icarus/ledger/run_log.jsonl` (hash-chained, reuse `Ledger.append` logic).
2. `icarus/primitives/verify.py`: replace own gates with a thin adapter that builds a
   `icarus/harness/runner.py` packet and returns its exit code + parsed stdout/stderr verdict.
   Keep the secret scan / allowed_commands veto as extra Gate 2 checks.
3. `icarus/primitives/daemon.py` (new): loop = fetch → claim one job → reasoner plan → execute in
   jobs dir → harness gate → append receipt → push → sleep. One job per cycle. Uses GH_TOKEN/TARGET_REPO env
   like `proxy_monitor.py`.
4. Container: add a NEW file `docker/Dockerfile.primitives` (do not edit `Dockerfile`).
5. Tests: update `tests/test_primitives.py` (git claims tested against a local bare repo in tmp_path,
   no network); run the full suite, not just this file.

## Must not
- Modify any existing file outside `icarus/primitives/` and `tests/test_primitives.py`
  (originals stay untouched; `Athena.gs`, `proxy_monitor.py`, `Dockerfile`, `icarus/harness/*`,
  `icarus/runtime/*`, `icarus/core/*` are read-only here).
- Merge to main, change the running container, or change Apps Script triggers/properties.
- Spend money or add paid services (default €0).

## Acceptance (verifier: Tier 1 machine, then an independent chair)
- `python3 -m pytest -q` full suite green inside `teamchat-harness:test`; exit code + SHA logged.
- `git diff --stat main...agent/icarus-primitives` shows only the allowed paths.
- Blob-SHA readback of every committed file matches local `git hash-object`.

## Next (needs owner yes, not this session)
- Pulse writes queued jobs into `icarus/ledger/queue/` (an `Athena.gs` change = production).
- Decide where the daemon container runs 24/7 (laptop vs always-on box).
- Reconcile pulse models (Gemini/OpenRouter) with the 23 Oct subscription-only decision.
