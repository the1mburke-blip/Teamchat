# HumanVibe Buffer Queue State

SNAPSHOT_GENERATED_UTC: 2026-10-01T08:41:08Z
SOURCE: Buffer live read via connected Composio account `HumanVibe Buffer` using authenticated `BUFFER_LIST_POSTS`.
AUTO_REFRESH: CONNECTOR_PATH_PROVEN
NEEDS_REFILL: NO
TARGET: 9 scheduled posts per channel
REFILL_THRESHOLD: below 6 scheduled posts on any channel

| Channel | Scheduled | Target | State | Next due UTC |
|---|---:|---:|---|---|
| Facebook | 8 | 9 | OK | 2026-10-01T12:00:00Z |
| Instagram | 8 | 9 | OK | 2026-10-01T12:00:00Z |
| Threads | 8 | 9 | OK | 2026-10-01T12:00:00Z |

CADENCE: 09:00 / 13:00 / 19:00 Europe/Dublin for 2026-10-01 through 2026-10-03.
PUBLISHER: Buffer only.
EXECUTION_ROUTE: Existing authenticated Composio Buffer connection -> Buffer GraphQL/API route.
VERIFICATION: 24 scheduled posts physically reread from Buffer at 2026-10-01T08:41:08Z; 8 per active channel; every returned item status=scheduled, share_mode=customScheduled, media asset present, publishing_error=null.
CONTINUITY_NOTE: The 09:00 Europe/Dublin slot on 2026-10-01 is no longer in the scheduled queue; the remaining live queue is 8/channel. This is above the refill threshold and requires no refill.

PRIME_ACTION_IF_NEEDS_REFILL: Perform the current daily HumanVibe research/status scan, then route refill through the established Prime -> Grace handoff. Keep Buffer as sole publisher and use the same authenticated Buffer API/proxy path when the high-level wrapper lacks required media/type fields.

## Window
- 2026-10-01 remaining: Facebook 2 / Instagram 2 / Threads 2
- 2026-10-02: Facebook 3 / Instagram 3 / Threads 3
- 2026-10-03: Facebook 3 / Instagram 3 / Threads 3
