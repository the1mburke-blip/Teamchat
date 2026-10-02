# HV-EXP-076 — Buffer media publishing wrapper gap: reuse authenticated native API beneath the wrapper

- experience_id: HV-EXP-076
- date_utc: 2026-10-02
- source_agent: ChatGPT duty manager
- task_problem: Restore HumanVibe's Buffer-only media publishing remotely while the owner was away from the laptop, at €0, without browser automation or direct-to-social bypass.
- failure_signature:
  1. Composio's `BUFFER_PUBLISH_POSTS` wrapper exposed text/channel/schedule fields but omitted Buffer's media `assets` field.
  2. Re-authorizing Buffer succeeded but did not change that wrapper schema, proving the blocker was not OAuth state.
  3. Existing Instagram failures also showed that service-specific media validation must be treated separately from the wrapper capability gap.
- root_cause:
  - Buffer's underlying API supported media posts, but the higher-level Composio Buffer action did not expose the media input.
  - Authentication and provider capability were healthy; the limitation existed at the wrapper/tool-schema layer.
- successful_recovery:
  - Reused the newly ACTIVE Buffer OAuth connection through Composio's authenticated `proxy_execute` path.
  - Verified direct Buffer GraphQL authentication with an account read.
  - Called Buffer's native `createPost` mutation with `assets.image.url` using existing public Shopify CDN media.
  - Added required service metadata after evidence-matched validation: Instagram `type: post` / share-to-feed metadata; Facebook `type: post`.
  - Replaced the failed Instagram publication through Buffer; replacement post `6abfa8925f7061ee2f1561a8` read back `status=sent`, `publishing_error=null`, with JPEG media attached.
  - Refilled the Buffer queue and independently read it back at 30 scheduled posts: 10 Facebook, 10 Instagram, 10 Threads; all 30 carried media assets.
- verification_evidence:
  - Direct Buffer account GraphQL read succeeded through the authenticated proxy.
  - Controlled media test post `6abfa853e11203baed26860f` was accepted as scheduled with `image/jpeg` asset.
  - Failed-slot replacement `6abfa8925f7061ee2f1561a8` was physically read back as sent at 2026-10-02T12:50:35.885Z with no publishing error.
  - Final Buffer readback: scheduled_total=30; per-channel counts=10/10/10; scheduled_with_assets=10/10/10.
- what_not_to_retry:
  - Do not repeatedly re-authorize Buffer expecting the Composio wrapper schema to gain media fields.
  - Do not use browser automation merely to compensate for a wrapper-schema omission when the authenticated lower-level provider API is available.
  - Do not bypass the protected Buffer publishing lane by posting directly to Instagram/Facebook/Threads.
  - Do not substitute text-only posts when the governing cadence requires text/photo.
  - Do not confuse provider capability, connector authentication, wrapper capability, and platform media validation; test each layer separately.
  - Do not retry Shopify URL-parameter-only image transforms as proof of valid Instagram dimensions; HV-EXP-072 remains authoritative for that failure mode.
- reusable_principles:
  - **When a connector wrapper lacks a provider feature, verify the provider contract before declaring the capability unavailable.**
  - **If OAuth is healthy, reuse that authenticated connection at the lowest approved API layer rather than creating duplicate credential infrastructure.**
  - **Separate transport/auth failures, wrapper-schema gaps, and destination-platform validation failures; they are different layers and need different evidence.**
  - **Use one controlled write with a previously proven asset, then read back final effect before scaling the repair.**
  - **Service-specific metadata is part of the external contract: Facebook/Instagram post type must be supplied when Buffer requires it.**
- cost_note: €0. No Codex, paid API, browser automation, or new subscription used.
- owner_involvement: One Buffer OAuth approval tap; no laptop access required.
- confidence: HIGH
