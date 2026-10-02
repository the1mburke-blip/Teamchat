# Icarus Android — Blocker 1: Secure Composio execution boundary

- date: 2026-10-02
- status: RESOLVED_ARCHITECTURALLY
- cost_target: €0
- scope: Android Icarus mobile MVP
- desktop_hands: DeepSeek Harness (DSH)
- mobile_hands: Composio

## Blocker
A Composio project/user API credential must not be embedded in the Android APK. Composio API calls are key-authenticated, and a client-distributed secret cannot be treated as secret.

## Decision
Use a minimal Cloudflare Worker as the mobile execution broker.

### Flow
1. Android Icarus authenticates the user/device to the broker.
2. Broker maps that identity to a stable Icarus/Composio user ID.
3. Broker holds the least-privilege Composio credential as an encrypted Worker secret.
4. Broker creates or reuses a Composio session for that user.
5. Android requests an allowed action through the broker.
6. Broker executes through the user's Composio session/connected account.
7. Broker returns only the result/evidence required by Icarus.
8. Icarus verifies final effect and writes the checkpoint to shared cross-save state.

## OAuth/account connection
Use Composio Connect Links for provider authorization. Provider credentials remain in Composio; the Android app never receives raw Gmail/Drive/etc OAuth tokens.

## Permission model
Create a scoped Composio project key with only the minimum session-management and session-tool-execution permissions required by the MVP. Enable Proxy Execute only if a specific provider capability cannot be reached through a normal Composio tool.

## MVP security boundary
- Never ship a Composio project, organization, or user API key in the APK.
- Never persist provider OAuth tokens in Android storage.
- Keep the Composio key only as a Cloudflare Worker secret.
- Maintain a per-user Composio session and stable user ID.
- Restrict the broker to an allowlist of Icarus-approved tool operations.
- Verify result/effect before marking a task complete.

## Why Cloudflare Worker
Cloudflare Workers Free currently provides 100,000 requests/day and encrypted Worker secrets, sufficient for the MVP broker at €0.

## Cross-device architecture
Desktop: Icarus -> DSH -> external effect
Mobile: Icarus -> Worker broker -> Composio -> external effect
Both: shared Icarus cross-save/checkpoints/evidence

The hands differ by device. Icarus identity, task state, verification rules, and cross-save remain common.

## Remaining implementation gate
Implement one vertical slice:
Android request -> broker -> existing Composio connected account -> harmless real action -> readback -> verified result -> cross-save checkpoint.

PASS only when that physical loop succeeds with the PC off.
