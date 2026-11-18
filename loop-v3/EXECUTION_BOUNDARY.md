# Execution boundary repair (TASK-CLAUDE-EXECUTION-BOUNDARY-REPAIR-20261118, Teamchat #241)

Pipeline: Discover -> Validate -> Claim -> Execute -> Verify -> Complete, run by a plain CLI process, not a chat model.

| File | Role |
| --- | --- |
| `task_runner.py` | `--once` / `--poll N`: scan `task_queue/`, fail-closed ingress, claim, execute via `harness-runner-v3.py`, recover after interruption, persist `state/<task_id>.json` |
| `completion_gate.py` | independent verifier; `COMPLETE` is reachable only through `verify_completion()`; `--audit` re-verifies every state file claiming COMPLETE |
| `ingress_policy.json` | allowed authority scopes / executors. Missing file rejects everything |
| `tests/test_task_runner.py` | 29 tests: lifecycle, 11 rejection cases, 10 gate negatives, kill -9 + restart recovery, attempt cap |

Rules enforced in code:
- Reject (never repair) a packet that is not JSON, fails schema, lacks `authority_scope`, is outside the policy, breaks command scope / negative constraints, or holds a secret. A hash-chained `icarus/rejection.v3` receipt is appended to the ledger.
- State is written atomically (tmp + fsync + rename). The attempt counter is persisted before the stage runs, so a crash counts. Cap is 3 per task_id, also across changed packets. Same bytes after FAILED/BLOCKED are not re-run.
- A dead runner (pid gone or lease expired) moves EXECUTING to INTERRUPTED; the packet stays queued and is re-claimed. A live owner is never taken over.
- COMPLETE needs: exit 0 on every stage, outputs present and re-hashed, git SHA, schema valid, zero secrets (packet, outputs, log), negative constraints hold, ledger chain intact, receipt in ledger matching the state record, attempts <= 3. Then a `icarus/terminal.v3` receipt is appended.

Run: `python3 task_runner.py --once` (or `--poll 60`). Tests: `cd loop-v3 && python3 -m unittest discover -s tests`.

Known limit: this code is a runner, not a host. A process that polls unattended still needs a machine that stays on. This change adds no workflow, schedule or listener, and does not touch the Icarus pulse runner or dispatch Icarus.
