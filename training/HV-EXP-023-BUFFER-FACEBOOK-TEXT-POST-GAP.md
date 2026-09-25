# HV-EXP-023 — Buffer Facebook text-only create gap

- date_utc: 2026-09-25T06:22:00Z
- source_agent: SOL
- task_problem: Remove repetitive social imagery while preserving today's Buffer cadence.
- environment_context: HumanVibe Buffer via canonical Composio account; Facebook channel 6a9c0c92065799be469311a5.
- symptoms_failure_signature: BUFFER_PUBLISH_POSTS returned InvalidInputError: "Invalid post: Facebook posts require a type (post, story, or reel)."
- attempts_made: 1
- what_failed: After deleting one future Facebook post whose image duplicated the morning asset, the Buffer create wrapper could not recreate the Facebook post as text-only because its exposed schema has no Facebook post-type field.
- why_it_failed: The generic BUFFER_PUBLISH_POSTS wrapper is insufficient for this Facebook create path; its input schema does not expose the required Facebook type.
- successful_recovery: NONE. Slot remains intentionally unfilled rather than bypassing the Buffer-only publishing rule.
- verification_evidence: Composio execution log log_dzGI3oASGPT8; provider failure_count=1, success_count=0, code=InvalidInputError.
- what_not_to_retry: Do not use BUFFER_PUBLISH_POSTS to recreate a Facebook text-only post until the wrapper exposes the required Facebook post type or a verified Buffer-native edit/create route exists.
- reusable_principle: Verify replacement capability before deleting an existing scheduled post. When Buffer-only governance applies, do not bypass a wrapper gap with direct social APIs.
- capability_tool_prerequisites: A Buffer-native create/edit action exposing Facebook post type and, for visual repair, media attachment support.
- confidence: HIGH
