# Icarus text-first prototype candidate

Status: PARTIAL; source and deterministic tests, no live deployment or phone verification.
Proposed by Michael; actual implementation executor ChatGPT Work/Codex worker; 6 October 2026. External cost EUR0. Root independently verifies repository/CI; Michael owns standalone phone acceptance.

## Reused route and changes

Signed Android -> existing task store -> autonomous one-shot continuation (existing recurring trigger is fallback) -> mandatory Gemini Direct -> existing Composio Gmail/Drive read-only tools -> repeat-read verification -> persisted result and owner-verification boundary.

`server-overlay` contains six overlays only. Overlay on a fresh export of the SAME Apps Script project. Unchanged GoogleIdentity/SignedAuth/StateStore/Genome/OwnerVerification and other runtime files remain required; this directory is not a new Apps Script project.

- Code: persist signed intake and return the canonical task before remote reasoning; scheduling failure logged without destroying task.
- Runtime: Gemini mandatory; lock-coalesced trigger; remove fired trigger before draining so a concurrent submit can schedule continuation. Recover timer-eligible reasoning/execution/verification tasks; interrupted reasoning becomes explicit BLOCKED instead of permanently polling.
- Provider: existing function-call contract and capability gate; deny NONE/mock provider for prototype.
- Composio: restrict to Gmail/Drive read tools, deny mutation slugs before explicit allowlists; preserve existing active-connection/account-selector repair and repeat-read. Permit read-only verification recovery.
- Enrollment/Auth: reuse strict existing Google owner ID-token validator and nonce challenge pattern; configured identity/capability mandatory, device UUID-bound 300s single-use nonce, active UUID replacement denied, shared token mint/hash helper preserves legacy pairing behavior. No Session effective-user authorization.
- Android: Google consent requests existing server audience and server nonce; token sent directly to same allowlisted backend, returned device token Keystore-encrypted then signed runtime readback. Recovery fields are optional advanced controls. Reuse signed-v1 and Keystore-encrypted token, same application identity/default signing semantics. Store accepted task ID for restart/manual refresh; same-objective pending submit reuses clientTaskId after response loss; composer released after wait. No voice promise.

## Verification available

`node tests/runtime.test.cjs` uses exact repository SignedAuth, StateStore, GoogleIdentity and Utils baseline fixtures plus candidate Code/Runtime/Provider/Composio/Auth/Enrollment. It exercises real intake/replay/idempotency/state transitions/provider parser and wrong-owner/nonce/audience/issuer/expiry/verified-email/config/capability/device/challenge replay/conflict denials, plus fresh owner enrollment -> signed runtime and no tokens in logs; service transports and Google sheets are synthetic. No API spend or private mailbox data. Integration test results do not prove a physical Redmi endpoint.

Branch-only workflow `.github/workflows/icarus-prototype-candidate.yml` runs tests and assembles release UNSIGNED inspection APK. No API secrets, deployment or installation. Stable Android 36/dependency versions are reused from the existing successful build lane. Retained signing-key availability is UNKNOWN. Root inspected the original September22 release archive (SHA256 7ae0a7f9675ba25704d484ac47ec0c83a109944cf9061e1ec5b9c9e927b03c3f;77 entries): it contained no APK/keystore/JKS/p12/pfx/pem/key or signing-named file. That is evidence about this archive only, not global absence. An unsigned artifact is not install-ready and cannot establish patch compatibility.

## Unresolved acceptance boundaries

1. Same-project Google deployment authority: existing OAuth relay timed out; do not replay it unchanged. Update existing deployment only after fresh source/rollback readback and authorized owner-local session.
2. Effective `provider.reason`, `PROVIDER_MODE=GEMINI_DIRECT`, Gemini free-billing/quota, and existing Composio properties/connections require fresh private live verification before canary. No blanket enablement.
3. Fresh no-manual-code enrollment is implemented in candidate source only, not deployed or physically proven. Existing configured GOOGLE_OAUTH_CLIENT_ID/OWNER_GOOGLE_EMAIL_SHA256 and effective owner.google_identity capability must be read back privately. Android OAuth client for the retained package/signing fingerprint must already be accepted by the same Google project; CredentialManager consent must succeed on the actual Redmi. No API key/Google token/device token is embedded. Public same-deployment URL is prefilled. Legacy pairing stays available but is not the normal install flow.
4. Retained Android signing key and installed identity must be verified before producing an installable patch; this candidate does not generate a new signing identity.
5. One fresh Redmi-origin task with PC/Codex/ADB absent must reach Gemini, Composio and same-task phone result, then match independent Gmail/Drive read and Michael verification. No PASS from this worker.

Known further runtime limitation: Apps Script one-shot trigger timing is not guaranteed to fit the Android 60-second polling window; saved-task refresh supports later readback. Scheduler installation/permission must be physically verified at deployment.
