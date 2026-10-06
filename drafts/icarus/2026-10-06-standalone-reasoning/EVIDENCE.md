# Icarus standalone reasoning — repo worker evidence packet

Status: INPUT SNAPSHOT FOR REPO WORKER
Date: 2026-10-06
Issue: #55
Cost target: €0

## Direct live evidence
- Current live Apps Script project was exported from the connected owner Drive before this worker was created.
- Android-origin tasks after Gemini activation show REASONING provider=GEMINI_DIRECT and READY_FOR_EXECUTION in the Control Plane.
- Therefore Gemini transport itself is not the unproven component.
- Current live Code.gs handles submit by createTask_() followed by synchronous advanceTask_() before returning a task response.
- Current status operation only auto-advances PENDING_AUTH.
- Current recurring resumePendingTasks_ eligibility is QUEUED, INSPECTING, EXECUTING, VERIFYING; it intentionally excludes REASONING and WAITING_REASONING_CAPACITY.
- Current Setup.gs installs resumePendingTasks_ every 5 minutes.
- Owner-observed acceptance failure: with Codex/laptop disconnected, the phone does not complete the task.

## Worker target
Remove dependence on one long synchronous phone request for the submit -> reasoning transition.

Required contract:
1. submit persists the task and returns the canonical task ID quickly;
2. server-side Apps Script continuation advances the persisted task without Codex/ADB/laptop;
3. no duplicate Gemini attempt is introduced;
4. REASONING and WAITING_REASONING_CAPACITY remain excluded from blind timer retry;
5. existing signed-v1, provider, task objective, Composio, owner-verification, package/pairing and credentials remain untouched;
6. no new backend/provider/database/auth service;
7. no live deployment from this repo worker.

## Independent deterministic gates
The worker must produce a candidate that passes:
- Apps Script/JavaScript syntax checks;
- submit block contains no inline advanceTask_ call;
- submit returns taskForClient_ after scheduling server continuation;
- one-shot continuation is idempotently scheduled and invokes resumePendingTasks_;
- recurring fallback trigger cadence is 1 minute;
- resumePendingTasks_ still excludes REASONING and WAITING_REASONING_CAPACITY;
- Provider.gs, StateStore.gs and SignedAuth.gs are byte-for-byte unchanged from the live snapshot;
- no new external backend URL or credential is introduced.

Executor may not self-award PASS. Final endpoint remains a fresh Redmi task with Codex/ADB/laptop absent.
