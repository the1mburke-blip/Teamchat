# icarus/primitives — vendor-neutral core

Four files, no vendor APIs, standard library only. Standalone package: it does
not import or modify any other Icarus module.

| Primitive | File | Format / dependency |
|---|---|---|
| 1. State & evidence ledger | `ledger.py` | SQLite queue + hash-chained `run_log.jsonl` |
| 2. Execution engine | `runner.py` | one cycle per process; any scheduler |
| 3. Reasoning engine | `reasoner.py` | any OpenAI-compatible endpoint, JSON plan only |
| 4. Verification referee | `verify.py` | deterministic Gate 1 + Gate 2 receipt |

## Cycle
Wake → claim 1 job (atomic, expiring lease) → reasoner returns JSON plan →
runner executes in `jobs/<id>/attempt-N/` (argv only, no shell, path-confined,
allowlist vetoed before execution) → `verify.py` issues receipt →
ledger settles (`done` / re-`queued` / `BLOCKER_DISCOVERED` after
`max_attempts`) → exit.

## Mapping to `training/TASK_DELEGATION_TEMPLATE.json`
- Rule 1 / 3 — `verify_spec` (pass criteria) is required at `enqueue`, set by the
  task author; the executor never writes it. The receipt comes from `verify.py`.
- Rule 2 — Gate 1 (exit 0, files exist, sha256, git SHA) and Gate 2 (schema,
  zero secrets, negative constraints) both required for PASS.
- Rule 4 — `max_attempts` (default 3), 300 s per command.
- Rule 6 — `allowed_commands` vetoes before execution and is re-checked.
- Rule 7 — run log is append-only and hash-chained; `Ledger.verify_chain()`
  detects edits.
- Not here (on purpose): peer handoff (rule 5) and Tier 3 escalation act on
  `BLOCKER_DISCOVERED` jobs and belong to whoever reads the ledger.

## Run
```
export ICARUS_REASONER_URL=http://localhost:11434/v1   # e.g. local Ollama
export ICARUS_REASONER_MODEL=llama3.1
python3 -m icarus.primitives.runner --root icarus/primitives/state --runner-id laptop
```
Cron (hourly): `0 * * * * cd /path/to/Teamchat && python3 -m icarus.primitives.runner --root icarus/primitives/state --runner-id laptop`

Enqueue (task author):
```python
from icarus.primitives.ledger import Ledger
Ledger("icarus/primitives/state").enqueue(
    "T-001", task={...filled template...},
    verify_spec={"expected_files": ["out.txt"], "allowed_commands": ["python3"]},
    author="owner")
```

Tests: `python3 -m pytest tests/test_primitives.py -q`
