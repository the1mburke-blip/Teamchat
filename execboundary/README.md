# execboundary — external execution boundary (TASK-CLAUDE-EXECUTION-BOUNDARY-REPAIR-20261118)

`Discover → Validate → Claim → Execute → Verify → Complete`, standard library only, €0.
Not part of the Icarus pulse route. Does not dispatch Icarus. Does not modify `icarus/`, `.github/workflows/`, or `training/`.

## Run (any real shell: laptop, Docker, Codespace, CI)
```
python3 -m execboundary.runner --root STATE_DIR --repo GIT_WORKTREE --loop --interval 30   # unattended
python3 -m execboundary.runner --root STATE_DIR --repo GIT_WORKTREE --once                  # one cycle
python3 -I -m execboundary.verifier --root STATE_DIR --repo GIT_WORKTREE TASK_ID              # independent re-check
```
Drop an envelope (`{"envelope_version":"execboundary/1","packet":<v3 packet>,"execution":{...}}`) into `STATE_DIR/inbox/`.
If git or a git worktree is missing the runner exits 3 with `BLOCKED: execution capability absent` — it never simulates.

## Guarantees (each covered by `tests/test_execboundary.py`)
- **Fail-closed ingress** (`schema.py`): exact key sets, no duplicates, no placeholders, `template_version == v3.0.0`,
  `immutable_execution_rules` and adjudication gates byte-equal to `training/TASK_DELEGATION_TEMPLATE.json`,
  attempt_limit ≤ 3, timeout ≤ 300, argv lists only (no shell), no path escape, no outputs inside protected paths,
  principal in `authority.json`. Rejections get a write-once receipt and the input is moved to `rejected/`.
- **Persistent state + recovery** (`store.py`, `runner.py`): O_EXCL claim (one executor), per-attempt timestamps,
  exit codes, log hashes, output hashes, git SHA, forbidden-path fingerprint. A dead executor's RUNNING task is marked
  INTERRUPTED and re-run on restart. Identical packet after failure = `BLIND_RETRY` rejection. 3 attempts → `BLOCKER_DISCOVERED` + dossier receipt.
- **Independent completion gate** (`verifier.py`): separate `python -I` process; re-hashes and re-validates the stored
  packet, cross-checks exit codes with the EXECUTED receipt, re-hashes outputs, confirms the git SHA is a real commit,
  scans outputs/logs for secrets, checks forbidden paths/patterns, runs the packet's tests itself, verifies the ledger chain.
  `Store.complete()` is the only writer of COMPLETE and refuses any verdict that is not the verifier's with all 7 gates true.
- **Append-only ledger**: `ledger.jsonl` rows are sha256-chained; receipts are O_EXCL, mode 0444.

## Trust boundary (stated, not hidden)
Same-user processes can still edit state files; the inbox directory must be owner-controlled; `authority.json` names
principals but does not cryptographically authenticate a packet. Scheduled unattended running on GitHub Actions would
need state persistence and a workflow on `main` — an owner decision, not included here.
