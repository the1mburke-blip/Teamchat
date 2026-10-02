# Icarus Android — Blocker 2: Phone-alone reasoning provider

- date: 2026-10-02
- status: RESOLVED_FOR_MVP
- cost_target: €0
- scope: Android Icarus while desktop DSH is offline

## Blocker
The Android app needs a reasoning model even when the PC and DeepSeek Harness are unavailable. The model credential must not be embedded in the APK, and model failure must not destroy task state.

## Decision
Put model routing behind the same server-side broker used for Composio.

### MVP provider policy
1. Primary: Gemini Developer API free tier on an eligible Flash-class model.
2. Fallback: OpenRouter free route/model when Gemini is unavailable or quota-limited.
3. Never bind Icarus identity/task state to either provider.
4. Store provider credentials only as broker secrets.
5. Keep task_id, checkpoint sequence, mutation ledger, verified/pending steps and evidence outside the model session.

## Flow
Android voice/text -> Icarus task envelope -> broker -> selected model -> tool plan -> Composio execution -> final-effect verification -> cross-save checkpoint -> result to Android.

## Provider failover
A model/provider failure is not a task failure.
- checkpoint before provider switch
- do not repeat an unresolved mutation
- reconcile external state before retry
- continue the same task_id on the replacement model

## Privacy constraint
Google currently states free-tier Gemini content may be used to improve its products. Therefore:
- send the minimum provider/tool data needed for reasoning
- redact or summarize sensitive payloads where possible
- do not treat the free-tier provider as the final consumer privacy architecture
- keep the provider abstraction replaceable so a privacy-preserving paid or local option can replace it later without changing Icarus state or Composio hands

## Why not OpenRouter as primary
OpenRouter's current free plan is limited to 50 requests/day. It is useful as a zero-cost fallback/test provider, not the sole mobile brain.

## PASS gate
PC fully off:
Android query -> broker model -> Composio action -> independent readback -> same task_id checkpoint saved -> verified result returned.

No provider may self-certify PASS.
