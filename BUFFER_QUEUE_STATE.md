# HumanVibe Buffer Queue State

SNAPSHOT_GENERATED_UTC: 2026-09-30T23:38:22Z
SOURCE: Buffer live read via connected Composio account `HumanVibe Buffer` using the authenticated same-platform Buffer GraphQL/API route.
AUTO_REFRESH: CONNECTOR_PATH_PROVEN
NEEDS_REFILL: NO
TARGET: 9 scheduled posts per channel
REFILL_THRESHOLD: below 6 scheduled posts on any channel

| Channel | Scheduled | Target | State | Next due UTC |
|---|---:|---:|---|---|
| Facebook | 9 | 9 | OK | 2026-10-01T08:00:00Z |
| Instagram | 9 | 9 | OK | 2026-10-01T08:00:00Z |
| Threads | 9 | 9 | OK | 2026-10-01T08:00:00Z |

CADENCE: 09:00 / 13:00 / 19:00 Europe/Dublin for 2026-10-01 through 2026-10-03.
PUBLISHER: Buffer only.
EXECUTION_ROUTE: Existing authenticated Composio Buffer connection -> Buffer GraphQL createPost with assets + per-channel metadata + customScheduled.
ASSET_GATE: Production Asset Vault assets only; three approved model images were copied to stable Shopify CDN URLs for scheduling, with existing approved V2 mockups rotated after the six-post reuse window allowed them.
VERIFICATION: 27 scheduled posts physically reread from Buffer; every item status=scheduled, share_mode=customScheduled, media asset present, publishing_error=null.
CORRECTION: The three non-canonical Threads posts created earlier in the failed run were deleted before the canonical 27-post refill.

PRIME_ACTION_IF_NEEDS_REFILL: Perform the current daily HumanVibe research/status scan, then route refill through the established Prime -> Grace handoff. Keep Buffer as sole publisher and use the same authenticated Buffer API/proxy path when the high-level wrapper lacks required media/type fields.

## Window
- 2026-10-01: Facebook 3 / Instagram 3 / Threads 3
- 2026-10-02: Facebook 3 / Instagram 3 / Threads 3
- 2026-10-03: Facebook 3 / Instagram 3 / Threads 3
