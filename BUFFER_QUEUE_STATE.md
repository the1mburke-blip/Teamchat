# HumanVibe Buffer Queue State

SNAPSHOT_GENERATED_UTC: 2026-09-30T13:05:00Z
SOURCE: Buffer API live read via connected HumanVibe Buffer account
AUTO_REFRESH: ARMED_REQUIRES_BUFFER_API_KEY
NEEDS_REFILL: YES
TARGET: 9 scheduled posts per channel
REFILL_THRESHOLD: below 6 scheduled posts on any channel

| Channel | Scheduled | Target | State | Next due UTC |
|---|---:|---:|---|---|
| Facebook | 1 | 9 | CRITICAL | 2026-09-30T18:00:00Z |
| Instagram | 1 | 9 | CRITICAL | 2026-09-30T18:00:00Z |
| Threads | 1 | 9 | CRITICAL | 2026-09-30T18:00:00Z |

PRIME_ACTION_IF_NEEDS_REFILL: Before generating a refill handoff, perform the current daily HumanVibe research/status scan. Then route the refill task through the established Prime -> Grace handoff. This monitor is read-only and must not publish.

## Scheduled posts
- 2026-09-30T18:00:00Z | Facebook | 6ab919b4612c9e6ac925996a
- 2026-09-30T18:00:00Z | Instagram | 6ab919b470ec211d1d194802
- 2026-09-30T18:00:00Z | Threads | 6ab919b3612c9e6ac9259942
