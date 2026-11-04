# Pilot interface contract (v0.2, 4 Nov 2026)

Status: PARTIAL. Revised after the ChatGPT review of v0 (checkpoint 2 HOLD, 4 Nov). Written from repo evidence only. Nothing here has been run against the real laptop DSH.

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
- In harness mode, a hook request for a call_id the slot did not mint is denied and logged `UNPROPOSED_CALL`. The harness can only run what Icarus proposed.
- In harness mode the tool result comes back in the next slot request as a `tool` message. It is recorded with `source: harness_reported`. That is not independent evidence (section 6).

## 2. Shared authority (one Icarus, not three components)

The model slot, hook channel and supervisor are three surfaces of one controller. Each takes the same session record and writes the same ledger. [DECISION]

Session record (illustrative values):

```json
{
  "session_id": "s-20261104-001",
  "task_id": "T-0001",
  "issued_by": "owner",
  "execution": "harness",
  "grants": {
    "tools": ["read_file", "write_file"],
    "path_scopes": ["C:/Users/the1m/Icarus-Harness/work"],
    "max_calls": 50,
    "expires_at": "2026-11-04T23:59:00Z",
    "spend_eur": 0
  },
  "review_gates": [{"id": "g1", "after_calls": 10}],
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
- S6. Review gates (below).

### Review gates

Two different things are called 'checkpoint' in this project. They are kept apart.

1. The runtime step-count checkpoint in governed.py. The owner decided on 29 Oct that a step count must never end a task, because a count is not an owner-only boundary. That behaviour stays as it is.
2. Owner review gates: an opt-in list in the session grant, set by the owner, empty by default. When a gate fires the session goes PAUSED_FOR_REVIEW. [DECISION, pending owner confirmation]

While paused:
- the slot answers 409 and runs no model turn;
- the hook denies with reason PAUSED;
- the supervisor starts nothing new and does not kill a running child unless the grant says so.

Resume or stop comes only from a `resume` record from the owner or Icarus, never from the harness or the executing agent:

```json
{"gate_id": "g1", "decided_by": "owner", "decision": "resume"}
```

Limits: v0 authenticates a resume with the owner token on the control path. That does not protect against another process under the same OS account that can read the token. No tamper-proofing is claimed. [PROVISIONAL]

The build checkpoints in CHECKPOINTS.md are NOT this mechanism. They are the working procedure of the agent building this. Until session.py (checkpoint 3) lands, nothing in code enforces them.

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

Decision order, all failures are `deny`:
1. session valid and not paused;
2. `call_id` matches a call the slot minted and that is AUTHORIZED (harness mode), otherwise `UNPROPOSED_CALL`;
3. call not already EXECUTED, otherwise `DUPLICATE_EXECUTION`;
4. tool is in the grant;
5. real args inside the path scopes;
6. kernel check.

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

Any of these changes this contract. The contract does not change the evidence.
