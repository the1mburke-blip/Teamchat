# Pilot interface contract (v0, 4 Nov 2026)

Status: PARTIAL. Written from repo evidence only. Nothing here has been run against the real laptop DSH.

Every claim carries a tag:
- [REPO] read in a repo file (path and blob SHA given in section 0).
- [PROVISIONAL] inferred, or taken from a session summary. Must be confirmed inside the real harness at checkpoint 10.
- [DECISION] a design choice for this build, not a fact about any harness.

## 0. Evidence base (what was actually read)

| File (branch main) | Blob | What it establishes |
|---|---|---|
| icarus/checkpoints/2026-10-13-tether-and-learning/staged-tether/MODEL-SELECTOR.md | a66940ab | Installed desktop DSH was 0.2.0-rc.2 with Cordis 4.0.4 (12 Oct). DSH has a registered-model directory, supports local/OpenAI-compatible routes, and runs its model call under `llm/stream`. Hook signatures were taken from the locally installed library source, which is not in this repo. |
| icarus/checkpoints/2026-10-13-tether-and-learning/evidence/HARNESS-PATCH-REPORT.md | dcc7ae98 | DSH loads profile plugins and live-reloads them inside the running process (PID 15784 on 12 Oct). Native write/edit tools exist. The learned-memory integrity check does NOT intercept shell commands, external editors or all filesystem writes. No independent review. |
| icarus/checkpoints/2026-10-13-tether-and-learning/evidence/harness-runtime-evidence.json | fd684fad | Real activation evidence (PID, module hash, workspaces on C:\Users\the1m\...). The host is Windows. |
| dsh/provider.py, dsh/runner.py | cc68f19f, e58d8926 | NOT the installed harness. A small Python runner with hard-coded OpenRouter/DeepSeek URLs, no base-URL override, no hook or approval channel. It is not usable as evidence of how the real DSH is controlled. |
| icarus/agent/pilot/fieldguide.json | d0e1d34e | Seed hints, all UNVERIFIED by its own note. |

Not read, because it lives on the laptop: the installed DSH source, `.dsh/profiles/desktop/cordis.patch.yml`, the `icarus-gate` plugin and its `policy.json`. Anything depending on those is [PROVISIONAL].

## 1. Shared authority (one Icarus, not three components)

The model slot, hook channel and supervisor are three surfaces of one controller. Each takes the same session record and writes the same ledger. [DECISION]

Session record:
- session_id, task_id
- issued_by: `owner` or `icarus`. Never the harness.
- grants: allowed tools, path scopes, max calls, expiry, spend (default EUR 0)
- ledger: path of the single decision record

Ledger entry: seq, ts, session_id, task_id, surface (`slot`/`hook`/`supervisor`), kind, call_id, decision, reason, evidence, prev_hash, hash.

Rules:
- S1. No surface acts without a live session. Unknown or expired session = deny, and the denial is logged.
- S2. A request coming from the harness side cannot create or widen a grant.
- S3. One append-only, hash-chained ledger per session. If it cannot be written, every surface fails closed.
- S4. No surface writes PASS. Only the independent adjudicator's output can mark PASS.
- S5. Spend is EUR 0 unless the owner's grant says otherwise.

## 2. Model slot

- Binds 127.0.0.1 only, with a per-session bearer token. [DECISION]
- `POST /v1/chat/completions` and `GET /v1/models`, OpenAI-compatible. [PROVISIONAL] DSH registers local/OpenAI-compatible routes [REPO], but whether it accepts a localhost base URL, and which request fields it sends, is unverified.
- Must support streaming as well as plain responses, because DSH's model call runs under `llm/stream` [REPO]. The exact wire format is [PROVISIONAL].
- Every request goes slot -> session lookup -> GovernedCore -> reasoner. There is no code path from the slot to a reasoner that skips GovernedCore. [DECISION]
- Tool calls in a response are limited to tools in the session grant. Others are dropped and logged as `proposal_filtered`. [DECISION]
- If the reasoner pool is exhausted the slot answers 503 with a BLOCKED body and evidence. It never fabricates a completion.

## 3. Hook channel

- Request: session_id, call_id, tool, args, cwd. Response: decision (`allow` or `deny`), reason, ledger_seq. [DECISION]
- Check order: session valid -> tool in grant -> args inside path scope -> kernel check -> allow. Anything else is DENY. An unknown tool is DENY. [DECISION]
- Owner-only categories (credentials, legal, payment, security, safety): deny now and write an escalation record in the owner's format, `OWNER ASSISTANCE REQUIRED - [one exact action]` with `Evidence: [verified blocker]`. It never waits on the owner while blocking the session. [DECISION]
- Transport is [PROVISIONAL]. Two candidates: (a) DSH's own approval mechanism answered over localhost; (b) a thin forwarder plugin in the DSH profile that only relays requests and returns Icarus's decision. Which one DSH 0.2.x supports has not been read. The `icarus-gate` plugin (allow/deny/ask policy, decisions log) is known only from session notes.
- If the forwarder or hook is missing or disabled, Icarus reports `GAP: hook channel not attached`. He does not claim governance over calls the channel never saw.
- Coverage check: any execution the supervisor observes without a matching hook decision is logged as `UNGOVERNED_EXECUTION`. The patch report confirms some native paths (shell, external editors) are not intercepted by DSH's own checks [REPO], so this gap is expected, not hypothetical.

## 4. Supervisor

- Launch with an argument list, never a shell. Explicit environment allowlist. Fixed working directory. New process group. [DECISION]
- The host is Windows [REPO], so tree termination must work there (job object or `taskkill /T`). Tests run on Linux, so Windows behaviour is [PROVISIONAL] until checkpoint 10.
- Control is claimed only for processes Icarus launched: pid, creation time, executable path and argv hash are recorded. Attaching to an already-running DSH (PID 15784 existed on 12 Oct [REPO]) gives `OBSERVE_ONLY`, never `CONTROL`. [DECISION]
- Lifecycle: start -> health check -> running -> stop with grace period -> kill tree -> verify the tree is gone. Timeouts and crash detection record exit codes. No automatic restart (no blind retries).
- Evidence per run: argv, pid, start and exit time, exit code, capped stdout/stderr, and proof the tree is gone.
- The real DSH launch command and arguments on the laptop are unknown. [PROVISIONAL]

## 5. Reporting

- PASS: only from the independent adjudicator. PARTIAL: what is proven and what is not. BLOCKED: the blocker with evidence.
- A surface that cannot do something reports a GAP naming the exact operation and boundary. It does not claim authority it lacks.

## 6. What would falsify this contract (checkpoint 10 probes, inside the laptop DSH)

1. DSH rejects a localhost base URL, or sends a request shape the slot cannot answer.
2. DSH's tool-call loop cannot consume tool calls produced through the slot.
3. DSH has no approval mechanism an external process can answer, and no forwarder route.
4. The forwarder can be disabled by the harness without Icarus noticing.
5. Tree termination leaves orphan children on Windows.
6. DSH executes tool calls with no hook decision (UNGOVERNED_EXECUTION) beyond the known shell/editor paths.
7. The installed DSH differs from 0.2.0-rc.2 / Cordis 4.0.4 (a 23 Oct reinstall is reported in session notes).

Any of these changes this contract. The contract does not change the evidence.
