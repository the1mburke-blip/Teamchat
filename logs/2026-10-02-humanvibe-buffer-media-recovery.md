# HumanVibe Journey — Remote Buffer media publishing recovery

- date_utc: 2026-10-02
- status: PASS
- priority: Sale #1 continuity
- context: Owner was away from home until Sunday; repair had to be completed from the existing remote tool surface with no laptop dependency and €0 spend.

## What broke

HumanVibe's Buffer queue could be read through Composio, but the exposed `BUFFER_PUBLISH_POSTS` action could only create text posts. Re-authorizing Buffer did not add media fields. The failure was therefore isolated to the wrapper schema, not the Buffer account or OAuth connection.

A separate Instagram failure existed at the media-validation layer. This was not treated as proof that Buffer media publishing itself was unavailable.

## What fixed it

The existing ACTIVE Buffer OAuth connection was reused through Composio's authenticated low-level API proxy. Buffer's native GraphQL `createPost` mutation was then called with public Shopify CDN image URLs in `assets`.

Required platform metadata was learned through bounded live validation:
- Instagram: `type=post` and share-to-feed metadata.
- Facebook: `type=post`.
- Threads accepted the media post without the extra post-type field used by Facebook/Instagram.

The failed Instagram slot was republished through Buffer using a media asset that had already successfully published earlier that day.

## Physical evidence

- Replacement Instagram post: `6abfa8925f7061ee2f1561a8`.
- Readback: `status=sent`; `publishing_error=null`; JPEG asset attached.
- Sent timestamp: `2026-10-02T12:50:35.885Z`.
- Final scheduled queue: **30 posts**.
- Facebook: **10**.
- Instagram: **10**.
- Threads: **10**.
- Scheduled posts carrying media: **30/30**.
- After the three already-scheduled evening posts publish, the continuity queue returns to the agreed **27-post** target.

## Journey lesson

The shortest valid repair was not another authorization attempt, browser automation, a paid service, or a second publisher. It was to identify the exact failing layer and reuse the authenticated Buffer capability underneath the defective wrapper.

This preserves the governing architecture:

**Shopify media → authenticated Buffer API → Facebook / Instagram / Threads**

Buffer remains the publishing path. Composio remains useful as an authenticated transport/readback surface even when one high-level wrapper omits a provider feature.

- cost: €0
- owner_action: one OAuth approval tap
- protected_systems_bypassed: none
- browser_automation: not used
- direct_to_social_publishing: not used
