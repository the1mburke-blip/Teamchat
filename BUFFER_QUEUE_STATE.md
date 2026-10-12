# HumanVibe Buffer Queue State

SNAPSHOT_GENERATED_UTC: 2026-10-12T22:23:32Z
SOURCE: Independent fresh Composio session town, account HumanVibe Buffer Reauth, live BUFFER_LIST_POSTS per channel/status with pagination exhausted.
AUTO_REFRESH: NOT_PROVEN; this is a timestamped manual verified snapshot.
NEEDS_REFILL: YES
TARGET: 9 scheduled posts per channel
REFILL_THRESHOLD: below 6 scheduled posts on any channel

| Channel | Scheduled | Legacy errors | Target | Next due UTC | State |
|---|---:|---:|---:|---|---|
| Facebook | 3 | 0 | 9 | 2026-10-13T08:00:00Z | Below refill threshold |
| Instagram | 3 | 8 | 9 | 2026-10-13T08:00:00Z | Below refill threshold; old errors remain |
| Threads | 3 | 1 | 9 | 2026-10-13T08:00:00Z | Below refill threshold; old error remains |

CADENCE: 2026-10-13 09:00 / 13:00 / 19:00 Europe/Dublin (08:00 / 12:00 / 18:00 UTC).
PUBLISHER: Buffer only.
EXECUTOR: Actual Codex Work in SOL role, directly assigned by Michael; issue #94.
VERIFIER: Separate actual Codex editorial_qa agent. Editorial accepted packet SHA256 FCDC81DA9139B6401241E563A5EFFB495C3467B3B9032B2732F68ECA30CB3F67.
VERIFICATION: All nine exact captions, approved permanent image source URLs, unique IDs, due times, status=scheduled, publishing_error=null and sent_at=null independently reread. Independent readback log log_Vg4h3HdhbVEt. Separate native Buffer channel-state readback log log_tge0ZBB_wJWx confirms isQueuePaused=false, isDisconnected=false, isLocked=false for all three.
LEGACY_ERRORS: 9 counted in separate error-status reads before scheduling; retained unchanged. New posts have no errors.
STATUS: Nine-post rescue refill verified. Full delivery and ongoing continuity PARTIAL: no new post has been sent yet; target nine/channel not met.
TASK: https://github.com/the1mburke-blip/Teamchat/issues/94

## Scheduled post IDs

| Platform | 08:00 UTC | 12:00 UTC | 18:00 UTC |
|---|---|---|---|
| Facebook | 6acd5d355229b40e8683ee0b | 6acd5d5f9f22b96ae7e54008 | 6acd5d613d6121df4030f63b |
| Instagram | 6acd5d365229b40e8683ee96 | 6acd5d60aec88be081e6087c | 6acd5d629f22b96ae7e54071 |
| Threads | 6acd5d379f22b96ae7e533e7 | 6acd5d615229b40e8683f450 | 6acd5d625462be2e90278a7d |

PRIME_ACTION_IF_NEEDS_REFILL: Use live Buffer counts and current canonical owner/claim state before further refill. This snapshot supersedes the old 1 October NO-refill claim. Preserve one active owner, editorial/source review, approved media, rolling-six image rotation and no duplicate execution. Delivery must be physically verified after due time before declaring the full pipeline fixed.

## Previous snapshot retained for history (superseded)

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
