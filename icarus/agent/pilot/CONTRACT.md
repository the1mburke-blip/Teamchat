# Pilot interface contract (v0.3, 4 Nov 2026)

Status: PARTIAL. Revised after the ChatGPT reviews of v0 and v0.2 (checkpoint 2 HOLD, twice, 4 Nov). Written from repo evidence only. Nothing here has been run against the real laptop DSH.

Every claim carries a tag:
- [REPO] read in a repo file (path and blob SHA in section 0).
- [PROVISIONAL] inferred, or taken from a session summary. Must be confirmed inside the real harness at checkpoint 10.
- [DECISION] a design choice for this build, not a fact about any harness.

## 0. Evidence base (what was actually read)

| File | Blob | What it establishes |
|---|---|---|
| (main) icarus/checkpoints/2026-10-13-tether-and-learning/staged-tether/MODEL-SELECTOR.md | a66940ab | Installed desktop DSH was 0.2.0-rc.2 with Cordis 4.0.4 (12 Oct). DSH has a registered-model directory, supports local/OpenAI-compatible routes, and runs its model call under `llm/stream`. Hook signatures were taken from the locally installed library source, which is not in this repo. |
| (main) icarus/checkpoints/2026-10-13-tether-and-learning/evidence/HARNESS-PATCH-REPORT.md | dcc7ae98 | DSH loads profile plugins and live-reloads them inside the running process (PID 15784 on 12 Oct). Native write/edit tools exist. The learned-memory integrity check does NOT intercept shell commands, external editors or all filesystem writes. No independent review. |
| (main) icarus/checkpoints/2026-10-13-tether-and-learning/evidence/harness-runtime-evidence.json | fd684fad | Real activation evidence (PID, module hash, workspaces on C:\Users\the1m\...). The host is Windows. |
| (main) dsh/provider.py, dsh/runner.py | cc68f19f, e58d8926 | NOT the installed harness. A small Python runner with hard-coded OpenRouter/DeepSeek URLs, no base-URL override, no hook or approval channel. It is not evidence of how the real DSH is controlled. |
| (core) icarus/agent/governed.py | 7669b8a8 | GovernedCore.run() owns the whole loop. Reasoner output is a JSON proposal (parse_proposal). kernel.authorize() decides. Then run() itself calls hand.execute() and logs the result. Every max_steps it logs a `checkpoint` entry and keeps going. |
| (core) icarus/agent/hands.py | 2df4925a | Hand contract: tools(), execute(), probe(), stop(). LocalFilesHand.execute() runs read_file, list_dir, write_file. |
| (core) icarus/agent/pilot/fieldguide.json | d0e1d34e | Seed hints, all UNVERIFIED by its own note. |

Not read, because it lives on the laptop: the installed DSH source, `.dsh/profiles/desktop/cordis.patch.yml`, the `icarus-gate` plugin and its `policy.json`. Anything depending on those is [PROVISIONAL].

## 1. Who executes (resolves the v0 conflict)

Finding: GovernedCore.run() executes tool calls itself through its hand [REPO]. The v0 model slot returned tool calls for DSH to execute. Both cannot run the same call.

Rule: every session fixes ONE execution mode, and every call has exactly one executor. [DECISION]

| Mode | Who runs the loop | Who executes tools | What the model slot returns | Hand |
|---|---|---|---|---|
| core | Core (existing run()) | Core's hand | text only, never tool calls | the real hand |
| harness | the harness | the harness's own tools | OpenAI tool_calls minted by Core | NullHand that raises if called |

- core mode: the harness is used as a model consumer or as a hand adapter. run() is unchanged.
- harness mode needs a single-step entry point, because run() cannot hand a proposal back without executing it. Checkpoint 4 adds `GovernedCore.step()`: same prompt, parse_proposal, kernel.authorize and blind-retry rules as run(), but it never calls a hand. run() behaviour is unchanged and the existing 32 governed tests must still pass.
- Mixed mode (some tools by Core, some by the harness) is out of scope for v0.
- Call state machine, recorded in the ledger per call_id: PROPOSED -> AUTHORIZED (kernel check at proposal time) -> EXECUTED(by=core or harness; the hook re-checks the real arguments first) -> RESULT_RECORDED.
- A second EXECUTED for the same call_id is denied and logged `DUPLICATE_EXECUTION`.
- The proposal fixes the tool name and the exact arguments for that call_id. The hook lets the harness run that and nothing else (section 4).
- In harness mode, a hook request for a call_id the slot did not mint is denied and logged `UNPROPOSED_CALL`. The harness can only run what Icarus proposed.
- In harness mode the tool result comes back in the next slot request as a `tool` message. It is recorded with `source: harness_reported`. That is not independent evidence (section 6).

## 2. Shared authority (one Icarus, not three components)

The model slot, hook channel and supervisor are three surfaces of one controller. Each takes the same session record and writes the same ledger. [DECISION]

Session record (illustrative values; `0000000000000000000000000000000000000000000000000000000000000000` stands for a 64-character hash):

```json
{
  "session_id": "s-20261104-001",
  "task_id": "T-0001",
  "issued_by": "owner",
  "executor_id": "claude-build-01",
  "execution": "harness",
  "grants": {
    "tools": ["read_file", "write_file"],
    "path_scopes": ["C:/Users/the1m/Icarus-Harness/work"],
    "max_calls": 50,
    "expires_at": "2026-11-04T23:59:00Z",
    "spend_eur": 0
  },
  "checkpoint_plan": {
    "plan_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
    "approved_by": "owner-michael",
    "milestones": [
      {
        "id": "m1",
        "goal": "contract committed and read back",
        "grants": {"tools": ["read_file", "write_file"], "path_scopes": ["C:/Users/the1m/Icarus-Harness/work/docs"]},
        "evidence_required": ["commit_sha", "blob_verify"]
      },
      {
        "id": "m2",
        "goal": "session module with tests",
        "grants": {"tools": ["read_file", "write_file"], "path_scopes": ["C:/Users/the1m/Icarus-Harness/work/src"]},
        "evidence_required": ["commit_sha", "blob_verify", "test_run"]
      }
    ]
  },
  "reviewers": [
    {"id": "owner-michael", "role": "owner", "public_key_fingerprint": "sha256:0000000000000000000000000000000000000000000000000000000000000000"}
  ],
  "ledger": "icarus/runs/s-20261104-001.ledger.jsonl"
}
```

Ledger entry (illustrative values; `hash` is the SHA-256 of the canonical JSON of the entry without `hash`):

```json
{
  "seq": 5,
  "ts": "2026-11-04T18:20:00Z",
  "session_id": "s-20261104-001",
  "task_id": "T-0001",
  "surface": "slot",
  "kind": "proposal",
  "call_id": "call_s1_0005",
  "decision": "allow",
  "reason": "tool in grant, path in scope",
  "evidence": {"tool": "write_file", "args_sha256": "0000000000000000000000000000000000000000000000000000000000000000"},
  "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "hash": "0000000000000000000000000000000000000000000000000000000000000000"
}
```

Rules:
- S1. No surface acts without a live session. Unknown or expired session = deny, and the denial is logged.
- S2. A request coming from the harness side cannot create or widen a grant. `issued_by` is `owner` or `icarus`, never the harness.
- S3. One append-only, hash-chained ledger per session. If it cannot be written, every surface fails closed.
- S4. No surface writes PASS. Only the independent adjudicator's output can mark PASS.
- S5. Spend is EUR 0 unless the owner's grant says otherwise.
- S6. Review gates exist if and only if the session carries an approved checkpoint plan (2.1). They are not an optional setting.
- S7. `executor_id` names the agent doing the work. No approval counts if it comes from the executor (2.3).

### 2.1 Checkpoint plans and mandatory gates

Two different things are called 'checkpoint' in this project. They are kept apart.

1. The runtime step-count checkpoint in governed.py. The owner decided on 29 Oct that a step count must never end a task, because a count is not an owner-only boundary. That stays non-stopping. A count never creates or removes a gate.
2. Review gates. They come only from a checkpoint plan, and they are mandatory when a plan exists. [DECISION, review-aligned; owner confirmation requested]

Rules for plans:
- A task that has an approved checkpoint plan must run with it. The plan sits in the session record, pinned by `plan_sha256`, with `approved_by` naming a registered owner reviewer. Session creation fails closed if the plan is malformed, if a milestone has no `evidence_required`, or if the hash does not match.
- A plan cannot be dropped, edited or relaxed inside a session. Changing it means a new session approved by the owner.
- A session with no plan has no gates. That is the only way gates are absent, and the ledger records `no_plan` at session start so the absence is explicit.
- Each milestone carries its own grants (a subset of the session grants) and the evidence kinds it must show. Only the active milestone's grants apply. A call outside them is denied `OUT_OF_MILESTONE`. Work for the next milestone cannot start until this milestone's gate is resolved, so an executor cannot avoid a gate by never declaring a milestone.
- Gates mark milestones and evidence. Tool-call counts (`max_calls`) stay a budget, never a gate.

Declaring a milestone:

```json
{"milestone_id": "m1", "evidence": [{"kind": "commit_sha", "ref": "ffbad88c"}, {"kind": "blob_verify", "ref": "8f52df2f"}]}
```

Core checks mechanically that every required evidence kind is present. If not: `MILESTONE_INCOMPLETE`, no gate opens, work continues inside the same milestone. This checks that evidence is present, not that it is true. Truth is for the reviewer and the adjudicator.

On a complete declaration the session goes PAUSED_FOR_REVIEW and the ledger head hash at that moment is captured. While paused:
- the slot answers 409 and runs no model turn;
- the hook denies with reason PAUSED;
- the supervisor starts nothing new and kills nothing unless the grant says so.

Only a signed review decision (2.3) moves the session on. The last milestone's decision closes the plan. It is not PASS.

The build checkpoints in CHECKPOINTS.md are the working procedure of the agent building this. Until session.py (checkpoint 3) lands, nothing in code enforces them.

### 2.2 Why 'resume' is not a field the executor can fill in

See 2.3. The record below is a request for a decision, not a decision by itself.

### 2.3 Approval authority

- `reviewer_id` and any `decided_by` style field are lookup keys. They are never authority. A worker that writes `owner` into a record gets nothing. [DECISION]
- Authority is a valid signature over the decision, verifiable with the public key of a registered reviewer in the session's `reviewers` list. The registry is part of the owner-approved session record. The executor cannot edit it.
- The signed payload is: session_id, gate_id, milestone_id, ledger_head_hash, decision, nonce, expires_at. Binding to the ledger head means the decision approves the exact evidence state that was reviewed and cannot be replayed on another session or a later state. Each nonce is single-use.
- Separation of duties: the signer must be a registered reviewer whose role allows the decision, must not equal `executor_id`, and must not appear in this session's ledger as an acting surface. Otherwise `SELF_APPROVAL`, and the gate stays closed.
- Algorithm: asymmetric signatures (Ed25519), verified in Core against public keys only. Core never holds a private reviewer key. A shared token or HMAC is not acceptable, because anything that can verify could forge. If no vetted Ed25519 verifier is available where Core runs, the gate stays closed and the session is BLOCKED. There is no weaker fallback. [DECISION]
- Key custody: Core can verify a signature and registry membership. It cannot prove the private key was kept away from the executor. The owner's key must live somewhere the executor cannot read. That is an operational requirement code cannot prove. [PROVISIONAL]
- Opinions from reviewing agents (for example ChatGPT's reviews) are inputs. The owner, or Icarus acting as adjudicator, signs. A reviewing agent with no registered key cannot approve.

Review decision (illustrative values; `signature` is a placeholder):

```json
{
  "session_id": "s-20261104-001",
  "gate_id": "g-m1",
  "milestone_id": "m1",
  "ledger_head_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "decision": "resume",
  "nonce": "n-0001",
  "expires_at": "2026-11-04T19:00:00Z",
  "reviewer_id": "owner-michael",
  "signature": "base64-ed25519-signature-goes-here"
}
```

`decision` is `resume` (next milestone), `rework` (stay in this milestone) or `stop` (end the session).

## 3. Model slot: wire format

- Binds 127.0.0.1 only. Bearer token per session. [DECISION]
- `POST /v1/chat/completions` and `GET /v1/models`, in the standard OpenAI chat-completions format. [PROVISIONAL] DSH registers local/OpenAI-compatible routes [REPO], but whether it accepts a localhost base URL and which fields it sends is unverified.
- Every request goes slot -> session lookup -> Core -> reasoner. No code path from the slot to a reasoner skips Core. [DECISION]

### 3.1 Request

```json
{
  "model": "icarus",
  "messages": [
    {"role": "system", "content": "You are working in C:/Users/the1m/Icarus-Harness/work."},
    {"role": "user", "content": "Create notes.txt containing the word hello."}
  ],
  "tools": [
    {"type": "function", "function": {"name": "write_file", "description": "Write a file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}}
  ],
  "tool_choice": "auto",
  "stream": false,
  "temperature": 0,
  "max_tokens": 2048
}
```

Core builds its own prompt from identity, rules, memory and the task. The harness messages are context, not instructions. [DECISION]

### 3.2 Response: final text (core mode, or harness mode when the task is done)

```json
{
  "id": "icarus-0007",
  "object": "chat.completion",
  "created": 1793814000,
  "model": "icarus",
  "choices": [{"index": 0, "message": {"role": "assistant", "content": "notes.txt written."}, "finish_reason": "stop"}],
  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
  "icarus": {"session_id": "s-20261104-001", "ledger_seq": 7}
}
```

### 3.3 Response: tool call (harness mode only)

`arguments` is a JSON-encoded string, as in the OpenAI format. One tool call per response in v0; parallel tool calls are never emitted. `id` is minted by Core and becomes the ledger call_id.

```json
{
  "id": "icarus-0005",
  "object": "chat.completion",
  "created": 1793813990,
  "model": "icarus",
  "choices": [{"index": 0, "message": {"role": "assistant", "content": null, "tool_calls": [{"id": "call_s1_0005", "type": "function", "function": {"name": "write_file", "arguments": "{\"path\": \"notes.txt\", \"content\": \"hello\"}"}}]}, "finish_reason": "tool_calls"}],
  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
  "icarus": {"session_id": "s-20261104-001", "ledger_seq": 5, "call_state": "AUTHORIZED"}
}
```

A proposed tool call is emitted only if the tool is in the request's `tools` list AND in the session grant, its arguments parse as a JSON object, and kernel.authorize allows it. Otherwise it is not emitted, it is logged as `proposal_filtered`, and Core re-prompts with the blocker, as run() does.

### 3.4 Streaming

Governed output cannot be streamed before it is authorized. In v0 Core completes and authorizes the whole turn first, then emits it as chunks. [DECISION] It is a replay of a finished result, not token streaming from the reasoner. Whether DSH needs real streaming is [PROVISIONAL]; it calls the model under `llm/stream` [REPO].

Wire format, server-sent events, one JSON object per `data:` line:

```
data: {"id": "icarus-0007", "object": "chat.completion.chunk", "created": 1793814000, "model": "icarus", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "notes.txt written."}, "finish_reason": null}]}

data: {"id": "icarus-0007", "object": "chat.completion.chunk", "created": 1793814000, "model": "icarus", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}

data: [DONE]
```

For a tool call, the first chunk's delta carries `tool_calls` as a list with one entry: `index` 0, the minted `id`, `type` `function`, and `function` with `name` and the complete `arguments` string in a single delta. The final chunk has `finish_reason` `tool_calls`. Then `data: [DONE]`.

### 3.5 Tool results coming back (harness mode)

```json
{"role": "tool", "tool_call_id": "call_s1_0005", "content": "ok"}
```

The slot matches `tool_call_id` to a ledger call_id and records `tool_result` with the SHA-256 of the content and `source: harness_reported`. An unknown `tool_call_id` is logged `unmatched_tool_result` and is not trusted.

### 3.6 Errors

| Status | type / code | When |
|---|---|---|
| 400 | bad_request | malformed JSON or missing fields |
| 401 | auth | missing or wrong token, unknown or expired session (S1) |
| 409 | icarus_paused / PAUSED_FOR_REVIEW | a review gate is open |
| 503 | icarus_blocked / BLOCKED | reasoner pool exhausted, ledger unwritable, preflight failed |

```json
{
  "error": {"message": "reasoner unavailable: all routes exhausted", "type": "icarus_blocked", "code": "BLOCKED"},
  "icarus": {"session_id": "s-20261104-001", "ledger_seq": 8, "owner_action": "", "evidence": ["reasoner pool exhausted after 1 round"]}
}
```

The slot never fabricates a completion to avoid an error.

## 4. Hook channel: wire format

Transport is [PROVISIONAL]. Two candidates: (a) DSH's own approval mechanism answered over localhost; (b) a thin forwarder plugin in the DSH profile that only relays requests and returns Icarus's decision. Which one DSH 0.2.x supports has not been read. The `icarus-gate` plugin (allow/deny/ask policy, decisions log) is known only from session notes. The payloads below are the contract the forwarder or adapter must meet. [DECISION]

Request, `POST /hook` on 127.0.0.1 with the session bearer token:

```json
{
  "session_id": "s-20261104-001",
  "call_id": "call_s1_0005",
  "tool": "write_file",
  "args": {"path": "notes.txt", "content": "hello"},
  "cwd": "C:/Users/the1m/Icarus-Harness/work",
  "harness": "dsh",
  "harness_version": "unknown"
}
```

Response:

```json
{
  "decision": "allow",
  "reason": "matches AUTHORIZED call, args inside path scope",
  "ledger_seq": 6,
  "escalation": null
}
```

Owner-only decisions (credentials, legal, payment, security, safety) answer `deny` and fill `escalation`:

```json
{
  "decision": "deny",
  "reason": "owner-only boundary: credentials",
  "ledger_seq": 9,
  "escalation": {"category": "credentials", "owner_action": "OWNER ASSISTANCE REQUIRED - sign in to the provider", "evidence": "tool requested a credential field"}
}
```

Decision order, every failure is `deny` and is logged:
1. session valid, not paused, and a milestone is active;
2. `call_id` matches a call the slot minted (harness mode), otherwise `UNPROPOSED_CALL`;
3. call state is AUTHORIZED: not already EXECUTED (`DUPLICATE_EXECUTION`) and not burned (`CALL_BURNED`);
4. tool name equals the proposed tool name, otherwise `TOOL_MISMATCH`;
5. exact arguments equal the proposed arguments (below), otherwise `ARGS_MISMATCH`;
6. tool is in the active milestone's grants (`OUT_OF_MILESTONE`) and the real arguments are inside its path scopes;
7. kernel check.

Argument binding:
- At proposal time Core records the `tool` and the canonical arguments: the parsed JSON object, keys sorted, no insignificant whitespace, UTF-8. The SHA-256 of those bytes is `args_sha256` and goes in the ledger. The canonical bytes go to a capped side file named by call_id so a mismatch can be diffed.
- At hook time Core canonicalises the received `args` the same way and compares hashes. It never trusts a hash sent by the harness. Equality is exact: no fuzzy matching, no filled-in defaults, no path normalisation.
- A mismatch denies the request and burns the call_id. Later hook requests with that call_id are denied even with the correct arguments. This stops probing. Core must propose again to get a new call_id.
- If DSH rewrites arguments before it calls the hook (adds defaults, normalises paths), every call will mismatch. That is not loosened here. It shows up at checkpoint 10 as a falsifier, and the fix is an adapter that submits the original arguments.
- The tool result record (3.5) carries the call_id and the `args_sha256` it answers.

An unknown tool is deny. Escalation to the owner happens only for the owner-only categories, and it never leaves the session waiting. [DECISION]

If the forwarder or hook is missing or disabled, Icarus reports `GAP: hook channel not attached` and claims no governance over calls the channel never saw.

## 5. Supervisor: wire format

- Launch with an argument list, never a shell. Explicit environment allowlist. Fixed working directory. New process group. [DECISION]
- The host is Windows [REPO], so tree termination must work there (job object or `taskkill /T`). Tests run on Linux, so Windows behaviour is [PROVISIONAL] until checkpoint 10.
- Control is claimed only for processes Icarus launched: pid, creation time, executable path and argv hash are recorded. Attaching to an already-running DSH (PID 15784 existed on 12 Oct [REPO]) gives `OBSERVE_ONLY`, never `CONTROL`. [DECISION]
- Lifecycle: start -> health check -> running -> stop with grace period -> kill tree -> verify the tree is gone. Timeouts and crashes record exit codes. No automatic restart (no blind retries).
- The real DSH launch command and arguments on the laptop are unknown. [PROVISIONAL]

Event written to the ledger (kinds: launched, healthy, stdout, stderr, exit, stop_requested, killed, tree_gone, observe_only):

```json
{
  "surface": "supervisor",
  "kind": "exit",
  "session_id": "s-20261104-001",
  "pid": 4120,
  "create_time": "2026-11-04T18:21:00Z",
  "exe": "C:/tools/dsh/dsh.exe",
  "argv_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "exit_code": 0,
  "output_bytes": 2048,
  "output_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "tree_gone": true
}
```

Captured output goes to capped files. The ledger stores the path, size and hash.

## 6. Detection limits (what Icarus can and cannot see)

- Harness-reported events (tool results, stdout) come from the system being governed. They are evidence of what the harness says, not independent observation.
- Detection of execution outside the hook channel is [PROVISIONAL] and stays so until an independent observation mechanism is demonstrated. Matching hook decisions against harness-reported executions only catches a harness that reports honestly.
- The one independent mechanism planned: snapshot the hash tree of each scoped path before and after a supervised run. Any change with no matching approved EXECUTED call is logged `UNEXPLAINED_CHANGE`. It covers file effects only. It does not cover network calls, shell side effects outside the scoped paths, or anything outside the snapshot. [PROVISIONAL until demonstrated]
- The patch report confirms DSH's own integrity checks do not intercept shell commands or external editors [REPO], so gaps outside the hook channel are expected.

## 7. Reporting

- PASS: only from the independent adjudicator. PARTIAL: what is proven and what is not. BLOCKED: the blocker with evidence.
- A surface that cannot do something reports a GAP naming the exact operation and boundary. It does not claim authority it lacks.

## 8. What would falsify this contract (checkpoint 10 probes, inside the laptop DSH)

1. DSH rejects a localhost base URL, or sends a request shape the slot cannot answer.
2. DSH's tool-call loop cannot consume tool calls produced through the slot, or needs real token streaming.
3. DSH has no approval mechanism an external process can answer, and no forwarder route.
4. The forwarder can be disabled by the harness without Icarus noticing.
5. Tree termination leaves orphan children on Windows.
6. DSH runs tool calls with no hook decision beyond the known shell and editor paths.
7. The snapshot diff misses a change it should catch, or flags changes it should not.
8. The installed DSH differs from 0.2.0-rc.2 / Cordis 4.0.4 (a 23 Oct reinstall is reported in session notes).

9. DSH rewrites arguments before the hook sees them, so exact matching rejects legitimate calls.
10. No vetted Ed25519 verifier is available where Core runs, or the owner cannot keep a signing key away from the executor.

Any of these changes this contract. The contract does not change the evidence.
