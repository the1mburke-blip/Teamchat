# loop-v3: end-to-end autonomous loop (work branch)

Task: TASK-INIT-END-TO-END-CLOSED-LOOP-001 (Teamchat issue #216). Implementation lives here, in Teamchat,
not in ai-team-os (retargeted by Michael on 2026-11-13).

Flow: `task_queue/*.json` -> `icarus_pilot.py` -> `harness-runner-v3.py` (schema, scope, negative
constraints, secrets, Gate 1 + Gate 2) -> hash-chained `icarus/runs/RUN_LOG.jsonl` -> archive to `processed/`.
CI (`.github/workflows/loop-v3-gate.yml`) then attests the ledger (GitHub keyless attestation), posts one
receipt comment to issue #6 and reads it back.

Limits, stated up front:
- Work branch only. The workflow has no schedule and no listener; it runs on push to its branch or manual dispatch.
- The verifier here is Tier 1 machine. The author never grades its own work; an independent chair adjudicates.
- Merging to main needs owner approval.
- Prime Snapshot Sync reads only the latest 5 comments of issue #6, so a receipt leaves its window quickly.

Run tests: `cd loop-v3 && python3 -m unittest discover -s tests -v`
