# Icarus Mobile Hands — Blocker 7: Composio wrapper/tool gaps

- date: 2026-10-02
- status: RESOLVED_ARCHITECTURALLY
- cost_target: €0
- reference_incident: HV-EXP-076 Buffer media publishing

## Blocker
A predefined Composio tool can omit a provider capability even when the upstream provider API supports it. Treating the wrapper as the provider contract creates false blockers.

## Decision
Make provider-native Proxy Execute the standard second-stage fallback inside the mobile Composio hands layer.

## Execution ladder
1. Discover and use the normal Composio tool when it expresses the required action.
2. If the tool is missing an endpoint/field/request shape, verify the upstream provider contract.
3. Use session.proxyExecute() through the same user-scoped connected account.
4. Composio injects provider authentication server-side; never extract raw provider tokens.
5. Apply the same idempotency/reconciliation rules as any write.
6. Verify the final external effect independently.
7. Only declare a capability blocker if both the normal tool and the authenticated upstream API path are unavailable or forbidden.

## Security
- Proxy execution must be broker-side only.
- Use a scoped Composio project key with Proxy Execute permission only where needed.
- Maintain a toolkit/endpoint allowlist.
- Do not permit arbitrary client-supplied hostnames.
- Do not let the Android app set Authorization headers.
- Keep upstream provider domain restrictions intact.

## Retry rule
A proxied write is sent once. On timeout/5xx/unknown outcome:
- do not blindly retry
- read external state first
- reconcile using task_id/idempotency evidence
- retry only when safe

## PASS gate
Reproduce a predefined-tool omission in a test integration, complete the same final effect through Proxy Execute with the existing connected account, and read back the external state without exposing a raw provider credential.
