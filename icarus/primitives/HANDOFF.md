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

---

## [CLAUDE] HANDOVER 2026-11-17T23:48Z: ledger loop live end to end (for Icarus / DeepSeek chair)

Author: Claude Code (laptop session for Michael). Status: **PARTIAL** (self-verified; independent
verification and the Rule 43 compliance tracker are still open). Append-only: correct by new entry.

### 1. Endpoint reached (evidence you can check)
Owner `ICARUS_QUEUE` comment → Athena pulse enqueues → laptop daemon claims, plans, executes →
`icarus.primitives.verify` grades → state pushed → Athena relays the verdict to the source issue.

- Issue: https://github.com/the1mburke-blip/Teamchat/issues/237 ("[TEST] Daemon canary — ledger end-to-end").
- Final relay, 2026-11-17T23:47:11Z: `[ICARUS via runtime] Ledger job canary-003: PASS (verifier icarus.primitives.verify; not self-awarded).`
- Ledger branch `icarus-ledger`: `cc41d59` enqueue (23:42:11) → `4f5e329` claim (23:42:34) → `12441de` done (23:42:39).
- Receipt: gate_1 pass, gate_2 pass, `canary.txt` = "icarus canary ok",
  sha256 `675ec5a743f5f2d82e7e259962ecf5b24ae0958ac9611e7358b04beadd2854bb`, model gemini-3.5-flash-lite.

### 2. What is deployed right now
| Component | Where | Version / SHA |
|---|---|---|
| Pulse (Athena) | Apps Script project PrimeGeminiGmailBridge, files `Athena.gs` AND `Copy of Athena.gs` (both identical) | cloud-4.5, blob `3fe87900c702525a3b36ed683fc1b666d663f3e7`, commit `3b874f5` |
| Daemon | Docker container `icarus-primitives` on Michael's Windows laptop (`--restart unless-stopped`) | image `sha256:59c906f7…`, built from `b0b2324`, i.e. **without** `1b9addf` |
| Ledger | branch `icarus-ledger` (created from `main` at `a784eed`) | `icarus/ledger/{queue,claims,state}/`, `run_log.jsonl` (hash-chained) |
| Secrets | `%USERPROFILE%\.icarus\primitives.env` (user-only ACL), entered by Michael; never read by agents | n/a |
| Source branch | `agent/icarus-primitives` | head `1b9addf` |

Container start command (reuse it exactly; it does not read or print the env file):
`docker run -d --name icarus-primitives --restart unless-stopped --env-file "$env:USERPROFILE\.icarus\primitives.env" -e ICARUS_LEDGER_BRANCH=icarus-ledger -v icarus-ledger:/data/ledger -v icarus-work:/data/work --cap-drop ALL --security-opt no-new-privileges:true icarus-primitives`

### 3. What happened (chronological, with failure capture)
1. Docker Desktop up; worktree `$HOME\Teamchat-primitives` created from `agent/icarus-primitives`.
2. Michael ran `docker/setup-primitives.ps1` himself (secrets never passed through an agent).
3. FAIL: container restart-looped `set: Illegal option -`, because a Windows checkout gave the entrypoint CRLF.
   Fix `b0b2324`: `.gitattributes` `*.sh text eol=lf` (scoped to `*.sh`; a wider rule marked 42 CRLF-stored
   files dirty, including protected `icarus/core`, and was withdrawn before push). Lesson HV-EXP-173.
4. Rebuilt to include Michael's identity commit `5f7f855`; identity loads (13,957 chars).
5. Athena cloud-4.4 deployed (the live project was **cloud-4.2**, not 4.3). The built-in browser pane could not
   paste from the OS clipboard; Claude in Chrome could. Content verified by SHA-256 after reload.
6. FAIL `canary-001`: Athena enqueue got HTTP 409. Cause confirmed in Settings → Branches: `main` has
   "Require a pull request" and "Do not allow bypassing". Owner chose to keep `main` protected.
   Fix: branch `icarus-ledger`; Athena cloud-4.5 (`3b874f5`) runs only enqueue and relay on it via
   `onLedgerBranch_` (restores `R.branch`); test-ledger.js case 5 added; all 3 Athena suites green.
7. FAIL `canary-002` (correct behaviour): the model planned `python3`; the job's `allowed_commands` was
   `["echo","sh"]`, so the runner vetoed it on both attempts and the verifier said FAIL, giving BLOCKER_DISCOVERED.
   Relayed on #237 at 23:42:09Z. Root cause: the job spec was authored without knowing the reasoner's habits,
   and the reasoner was not told the limits. `1b9addf` (another chair) now shows the model
   `allowed_commands`/`expected_files`.
8. PASS `canary-003` (python3 allowed): see §1.

### 4. What we are waiting for
Nothing blocking. The loop is proven once. Open items are in §6.

### 5. How to track progress (no secrets needed)
- Issue thread: GET `https://api.github.com/repos/the1mburke-blip/Teamchat/issues/237/comments`.
  Athena receipts start `# Icarus run receipt v1`; verdict relays start `[ICARUS via runtime] Ledger job`.
- Ledger: `git fetch origin icarus-ledger` and then `git log origin/icarus-ledger`, `git show origin/icarus-ledger:icarus/ledger/state/<job>.json`.
- Daemon (laptop only): `docker ps --filter name=icarus-primitives`; `docker logs --tail 20 icarus-primitives`
  (JSON lines: `idle`, `queued`/`done`/`BLOCKER_DISCOVERED` with `verdict`); receipts in the container at
  `/data/work/<job>/attempt-N/receipt.json`.
- Timing: Athena polls every ≤10 min and handles one comment per poll, oldest first. The daemon polls every 60 s.
  The relay posts one final outcome per poll. Worst case comment → verdict ≈ 25 min.

### 6. Next best steps (in order)
1. **Prove `1b9addf` under the strict spec.** On the laptop: `git -C $HOME\Teamchat-primitives checkout --detach origin/agent/icarus-primitives`
   (expect `1b9addf`), rebuild (`docker build -f docker/Dockerfile.primitives -t icarus-primitives .`), `docker rm -f`, and
   run the command in §2. Do NOT rebuild while a job is claimed (check `docker logs`). Then post `ICARUS_QUEUE` **canary-004**
   on #237 with `allowed_commands: ["echo","sh"]` (the spec canary-002 failed). PASS proves the model now respects limits.
   Do not reuse job ids: queue files are immutable and Athena BLOCKs duplicates.
2. **Source drift (production risk).** `main` holds Athena cloud-4.3; live is cloud-4.5 (from `agent/icarus-primitives`).
   Open a PR `agent/icarus-primitives → main` so source of truth matches production. Needs owner review (main requires PRs).
3. **Rule 43 compliance tracker** for this run (separate task): known misses are listed in §7.
4. **Duplicate file**: `Copy of Athena.gs` duplicates every Athena function in the same Apps Script project. Owner decides
   whether to delete it; until then, every deploy must update BOTH files.
5. **Ledger/main divergence**: `icarus-ledger` only receives ledger commits. With `1b9addf` the daemon reads memory
   from `main`, so no sync is needed for memory; do not merge `icarus-ledger` into `main`.
6. Parked by owner: phone chat page (posts to issues; ≤10-min latency) and Slack channel (Slack connector not yet authorised).
7. 24/7 runner: the daemon runs only while the laptop and Docker Desktop are on; queued jobs wait.

### 7. Known process misses (for the compliance tracker)
- Elapsed-time estimate (~30 min) exceeded by more than 2×; GitHub token creation was not flagged as a risk in preflight.
- Line endings not checked before the owner's first setup run (one owner run wasted).
- `git add --renormalize .` staged 42 files including protected paths (caught before commit).
- Built-in-browser clipboard route attempted before checking that it supports OS paste.
- canary-001/002 specs authored without checking branch protection and reasoner command habits.
- `athenaSelfTest()` returns JSON without logging, so the "log line" evidence asked for cannot exist; evidence used instead:
  SHA-256 of both saved files after reload.

### 8. Do not
- Ask for, read, print or relay `GITHUB_PAT`, `GEMINI_API_KEY`, or the env file contents.
- Point ledger writes at `main` or weaken `main` protection.
- Edit `Athena.gs` in only one of the two Apps Script files.
- Self-award PASS: only the verifier receipt plus the Athena relay counts.

---

## [CLAUDE] ENTRY 2026-11-18: self-queue (cloud-4.6), STAGE_3/4 closed to owner merge

Author: Claude (chat session). Status: **PARTIAL** (self-verified; independent verification pending). Append-only.

- **Self-queue (gap: Icarus originates his own jobs).** `Athena.gs` cloud-4.6 adds `selfQueueTick_`: on an idle poll,
  at most once per 2 h and only when no ledger job is unfinished, Icarus reads the open board (receipt logs, rooms,
  tests and PRs excluded), picks one sandbox-safe item with the approved EUR 0 model, and writes
  `icarus/ledger/queue/auto-<UTC>-<issue>.json` on `icarus-ledger` with `author: icarus:pulse-self-queue`.
  The pulse sets the pass criteria (expected_files, allowed_commands echo/sh/cat/mkdir/python3, secret patterns
  forbidden); the daemon executes; the verifier grades; the existing relay posts the verdict to the picked item.
  An announcement comment (prefix `[ICARUS via runtime]`, cannot retrigger) goes on the item. Kill switch:
  script property `ATHENA_SELF_QUEUE_V1=off`. No new trigger: runs inside the existing 10-minute `athenaPoll`.
- Tests: `icarus/athena-gas/test-selfqueue.js` (6 scenarios) and `tests/test_primitives_selfqueue_bridge.py`
  (daemon ledger loads the self-queued file). Existing Apps Script suites set the kill switch so they keep testing
  comment replay only. Full suite: 299 passed, 30 subtests.
- **STAGE_3:** PR #239 (agent/icarus-primitives -> main) open; merge is owner-only (main requires reviewed PRs).
- **STAGE_4:** HV-EXP-174..178 in TRAINING_MATRIX.md; 12-rule tracker
  `logs/2026-11-17-icarus-ledger-loop-rule43-compliance.md` (7/12 PASS, R1/R2/R7 FAIL, R4/R10 UNVERIFIED; reviewer not independent).
- **Pin change:** branch head is no longer `1b9addf`. Daemon code is unchanged since `1b9addf`; a rebuild may check out
  this branch head. Only `Athena.gs` (production pulse) changed and needs deploying to both Apps Script files.

