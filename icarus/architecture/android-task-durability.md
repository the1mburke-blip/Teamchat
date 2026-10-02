# Icarus Android — Blocker 6: Task survives phone process death

- date: 2026-10-02
- status: RESOLVED_ARCHITECTURALLY
- cost_target: €0

## Blocker
Android may background, suspend, or kill the app after a user submits a task. Icarus must not lose the task or require a permanent phone foreground service.

## Decision
The Android app submits the task; a Cloudflare Workflow owns execution to completion.

Android is a controller/view, not the durable executor.

## Flow
1. Android creates a task envelope and sends it to the Icarus broker.
2. Broker allocates task_id and persists the initial checkpoint.
3. Broker starts one Cloudflare Workflow instance for that task.
4. Workflow performs durable steps:
   - load Icarus state/checkpoint
   - select reasoning provider
   - produce bounded action plan
   - execute through Composio
   - reconcile/read back external state
   - verify final effect
   - commit cross-save checkpoint/evidence
5. Initial Android request returns task_id immediately.
6. If Android remains open, it observes status.
7. If Android is killed, Workflow continues server-side.
8. On verified completion, send an FCM notification.
9. Android opens/resumes and reads the committed result.
10. WorkManager performs periodic/on-network resync if notification delivery is missed.

## Why not execute the task in WorkManager
WorkManager is for reliable Android-side deferred work, but Android process/job restrictions remain device/OS dependent. The task itself belongs above the device.

Use WorkManager only for:
- upload pending local checkpoint
- refresh task status
- resync Drive/broker head
- retry notification acknowledgement

## Free-tier fit
Cloudflare Workflows Free currently includes:
- 100,000 requests/day shared with Workers
- 3,000 Workflow steps/day
- 1 GB-month Workflow storage
- durable waits/retries
Firebase Cloud Messaging is currently a no-cost product.

## PASS gate
Submit a real task, then force-stop/kill the Android process before execution completes.
PASS only if:
- server task continues
- no duplicate external mutation occurs
- verified result commits to cross-save
- phone later receives or retrieves the completed result
- same task_id is preserved end-to-end
