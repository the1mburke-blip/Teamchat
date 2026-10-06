# Icarus text-first prototype candidate

Status: PARTIAL; source and deterministic tests, no live deployment or phone verification.
Proposed by Michael; actual implementation executor ChatGPT Work/Codex worker; 6 October 2026. External cost EUR0. Root independently verifies repository/CI; Michael owns standalone phone acceptance.

## Reused route and changes

Signed Android -> existing task store -> autonomous one-shot continuation (existing recurring trigger is fallback) -> mandatory Gemini Direct -> existing Composio Gmail/Drive read-only tools -> repeat-read verification -> persisted result and owner-verification boundary.

`server-overlay` contains four overlays only. Overlay on a fresh export of the SAME Apps Script project. Unchanged Auth/SignedAuth/StateStore/Genome/OwnerVerification and other runtime files remain required; this directory is not a new Apps Script project.

- Code: persist signed intake and return the canonical task before remote reasoning; scheduling failure logged without destroying task.
- Runtime: Gemini mandatory; lock-coalesced trigger; remove fired trigger before draining so a concurrent submit can schedule continuation. Recover timer-eligible reasoning/execution/verification tasks; interrupted reasoning becomes explicit BLOCKED instead of permanently polling.
- Provider: existing function-call contract and capability gate; deny NONE/mock provider for prototype.
- Composio: restrict to Gmail/Drive read tools, deny mutation slugs before explicit allowlists; preserve existing active-connection/account-selector repair and repeat-read. Permit read-only verification recovery.
- Android: reuse signed-v1 and Keystore-encrypted token, same application identity/default signing semantics. Store accepted task ID for restart/manual refresh; same-objective pending submit reuses clientTaskId after response loss; composer released after wait. No voice promise.

## Verification available

`node tests/runtime.test.cjs` uses exact repository SignedAuth and StateStore baseline fixtures plus candidate Code/Runtime/Provider/Composio. It exercises real intake/replay/idempotency/state transitions and provider parser; service transports and Google sheets are synthetic. No API spend or private mailbox data. Integration test results do not prove a physical Redmi endpoint.

Branch-only workflow `.github/workflows/icarus-prototype-candidate.yml` runs tests and assembles release UNSIGNED inspection APK. No API secrets, deployment or installation. Stable Android 36/dependency versions are reused from the existing successful build lane. Retained signing-key availability is UNKNOWN. An unsigned artifact is not install-ready and cannot establish patch compatibility.

## Unresolved acceptance boundaries

1. Same-project Google deployment authority: existing OAuth relay timed out; do not replay it unchanged. Update existing deployment only after fresh source/rollback readback and authorized owner-local session.
2. Effective `provider.reason`, `PROVIDER_MODE=GEMINI_DIRECT`, Gemini free-billing/quota, and existing Composio properties/connections require fresh private live verification before canary. No blanket enablement.
3. Fresh enrollment without manual pairing code is NOT solved. Existing pairDevice_ verifies Google owner identity if configured but separately requires a pairing-code hash; token returned only once and only its hash stored. Hash is not a recoverable token. Existing GoogleIdentity owner-token validator is a possible reusable basis for a separately authorized secure owner-enrollment repair, not current working enrollment.
4. Retained Android signing key and installed identity must be verified before producing an installable patch; this candidate does not generate a new signing identity.
5. One fresh Redmi-origin task with PC/Codex/ADB absent must reach Gemini, Composio and same-task phone result, then match independent Gmail/Drive read and Michael verification. No PASS from this worker.

Known further runtime limitation: Apps Script one-shot trigger timing is not guaranteed to fit the Android 60-second polling window; saved-task refresh supports later readback. Scheduler installation/permission must be physically verified at deployment.
