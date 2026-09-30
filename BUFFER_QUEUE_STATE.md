# HumanVibe Buffer Queue State

SNAPSHOT_GENERATED_UTC: 2026-09-30T23:25:46Z
SOURCE: Buffer live read via connected Composio account `HumanVibe Buffer` (account_id buffer_glisk-theer)
AUTO_REFRESH: CONNECTOR_PATH_PROVEN
NEEDS_REFILL: YES
TARGET: 9 scheduled posts per channel
REFILL_THRESHOLD: below 6 scheduled posts on any channel

| Channel | Scheduled | Target | State | Next due UTC |
|---|---:|---:|---|---|
| Facebook | 0 | 9 | CRITICAL | NONE |
| Instagram | 0 | 9 | CRITICAL | NONE |
| Threads | 3 | 9 | CRITICAL | 2026-10-01T11:30:00Z |

MONITOR_ROUTE: Read live queue through existing authenticated Buffer connector. Do not require or export a BUFFER_API_KEY.
REFILL_EXECUTION_STATE: PARTIAL — three compliant Threads text/link slots were restored for 2026-10-01 through 2026-10-03. The connected Composio Buffer publisher currently exposes text-only fields and does not expose Buffer's native `assets` or service metadata. Facebook scheduling through this wrapper fails with `Facebook posts require a type (post, story, or reel)`; Instagram media scheduling cannot be performed through this wrapper without bypassing the canonical Buffer-only publishing rule.
PRIME_ACTION_IF_NEEDS_REFILL: Perform the current daily HumanVibe research/status scan, then route only the unresolved media-capable Buffer refill work through the established Prime -> Grace handoff. Do not bypass Buffer with direct social publishing unless OWNER explicitly supersedes the protected Buffer-only rule.
GRACE_TASK_ID: BUFFER-QUEUE-REFILL-DAILY

## Scheduled posts
- 2026-10-01T11:30:00Z | Threads | 6abd9a515feb60d6345ffede
- 2026-10-02T11:30:00Z | Threads | 6abd9a5105e9a5c46ab01a02
- 2026-10-03T11:30:00Z | Threads | 6abd9a529b58fd09c05ce9a2
