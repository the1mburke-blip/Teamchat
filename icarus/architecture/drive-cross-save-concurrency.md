# Icarus Cross-Save — Blocker 3: Drive concurrency and state corruption

- date: 2026-10-02
- status: RESOLVED_ARCHITECTURALLY
- cost_target: €0
- durable_store: Google Drive
- sequencer: Icarus broker / Cloudflare Worker

## Blocker
Google Drive is suitable for durable portable state, but it is not a transactional database. Phone and desktop must not independently overwrite one mutable state file because stale writes could silently destroy newer task state.

## Decision
Keep Drive as the durable source of truth, but make the Icarus broker the single writer/sequencer for cross-save state.

Both mobile Icarus and desktop DSH submit state transitions through the same state-write contract.

## Write contract
Every state mutation carries:
- task_id
- device_id
- expected_revision
- idempotency_key
- mutation_ledger status
- verified_steps
- pending_steps
- evidence references
- payload hash

The broker:
1. reads the current task head
2. compares expected_revision
3. rejects stale writes instead of merging silently
4. reconciles unresolved external mutations before any retry
5. assigns the next monotonic revision
6. writes an immutable checkpoint/event to Drive
7. advances the task head
8. returns the committed revision and hash

## Drive layout
Icarus/
  identity/
  tasks/<task_id>/
    head.json
    checkpoints/000001.json
    checkpoints/000002.json
    events/000001-<hash>.json
    evidence/
  devices/<device_id>.json
  manifest.json

Checkpoint/event files are immutable. Only broker-controlled head/manifest pointers are mutable.

## Conflict behavior
If desktop and phone both start from revision 41:
- first valid write commits revision 42
- second write with expected_revision=41 is rejected as STALE_STATE
- Icarus loads revision 42, reconciles external effects, and creates a new valid revision only if needed

No silent last-write-wins merge.

## Sync/read behavior
- Devices cache the latest committed task state locally.
- On wake/resume, compare local revision to Drive/broker head.
- Google Drive change tracking/revision history may be used to reduce polling and aid recovery, but they are not the concurrency lock.

## Folder choice
Use a dedicated normal Drive folder owned by the user rather than appDataFolder for canonical cross-device state, so desktop and mobile runtimes can deliberately access the same durable records and the owner can inspect/export them.

## PASS gate
With desktop and phone starting from the same revision, intentionally race two writes. PASS only if one commits, the stale writer is rejected, no checkpoint is lost, and both devices converge on the same next state.
