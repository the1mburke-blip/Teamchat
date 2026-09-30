# HumanVibe Buffer Queue State

SNAPSHOT_GENERATED_UTC: 2026-09-30T14:04:01Z
SOURCE: Buffer live read via connected Composio account `HumanVibe Buffer` (account_id buffer_glisk-theer)
AUTO_REFRESH: CONNECTOR_PATH_PROVEN
NEEDS_REFILL: YES
TARGET: 9 scheduled posts per channel
REFILL_THRESHOLD: below 6 scheduled posts on any channel

| Channel | Scheduled | Target | State | Next due UTC |
|---|---:|---:|---|---|
| Facebook | 1 | 9 | CRITICAL | 2026-09-30T18:00:00Z |
| Instagram | 1 | 9 | CRITICAL | 2026-09-30T18:00:00Z |
| Threads | 1 | 9 | CRITICAL | 2026-09-30T18:00:00Z |

MONITOR_ROUTE: Read live queue through existing authenticated Buffer connector. Do not require or export a BUFFER_API_KEY.
PRIME_ACTION_IF_NEEDS_REFILL: Before generating a refill handoff, perform the current daily HumanVibe research/status scan. Then route the refill task through the established Prime -> Grace handoff. This monitor is read-only and must not publish.
GRACE_TASK_ID: BUFFER-QUEUE-REFILL-20260930

## Scheduled posts
- 2026-09-30T18:00:00Z | Facebook | 6ab919b4612c9e6ac925996a
- 2026-09-30T18:00:00Z | Instagram | 6ab919b470ec211d1d194802
- 2026-09-30T18:00:00Z | Threads | 6ab919b3612c9e6ac9259942
