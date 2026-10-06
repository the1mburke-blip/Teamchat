# Icarus text-first prototype candidate

Status: PARTIAL; source and deterministic tests, no live deployment or phone verification.
Proposed by Michael; actual implementation executor ChatGPT Work/Codex worker; 6 October 2026. External cost EUR0. Root independently verifies repository/CI; Michael owns standalone phone acceptance.

## Reused route and changes

Signed Android -> existing task store -> autonomous continuation -> mandatory Gemini Direct -> explicit native Google plugin for Gmail/Drive -> repeat-read -> persisted same-task result and owner verification. Google tasks make no Composio request. Unsupported legacy objectives retain their existing transport; mixed-service or unsupported Google requests block. This is a module inside the existing prototype, not an installed ChatGPT plugin/MCP server.

`server-overlay` contains nine source overlays including the preserved manifest with two added native Google scopes. Overlay on a fresh export of the SAME Apps Script project. Unchanged GoogleIdentity/SignedAuth/StateStore/Genome and other runtime files remain required; this directory is not a new Apps Script project.

- Code: persist signed intake and return the canonical task before remote reasoning; scheduling failure logged without destroying task.
- Runtime: Gemini mandatory; lock-coalesced trigger; remove fired trigger before draining so a concurrent submit can schedule continuation. Recover timer-eligible reasoning/execution/verification tasks; interrupted reasoning becomes explicit BLOCKED instead of permanently polling.
- Provider: existing function-call contract and capability gate; deny NONE/mock provider for prototype.
- GooglePlugin: single configured owner only. Verified enrollment persists server-trusted subject/email hash; scheduled execution rechecks ACTIVE device/owner capability/hash. Legacy devices without this marker must reenroll; recovery alone does not create it. Native `ScriptApp.getAuthorizationInfo(FULL, [service scope])` checks actual grants; null/errors return UNKNOWN. Backend OAuth token never leaves Apps Script. Fixed GET profile/about validates API principal against the configured owner hash before mailbox/file metadata. No Session effective-user caller authorization.
- Gmail: mailbox counts, or three selected messages’ From/Subject/Date headers via `format=metadata`; frozen IDs for repeat-read, no bodies/snippets/search/q. Drive: five recent file metadata records (id/name/mimeType/modifiedTime), no contents. Two reads must match before WORK_COMPLETE_AWAITING_OWNER_VERIFICATION; no worker PASS.
- Connections: signed status/authorize operations, strict native Google consent URL allowlist, Android external consent and explicit signed refresh. Callback success parameters have no authority. Missing/expired/denied grant stays PENDING_AUTH; unknown or wrong owner becomes BLOCKED. Calendar/Sheets are UNAVAILABLE.
- OwnerVerification: native stored result/log IDs participate in the existing same-task owner evidence fingerprint and challenge; strict original Google validator remains unchanged.
- Composio: restrict to Gmail/Drive read tools, deny mutation slugs before explicit allowlists; preserve existing active-connection/account-selector repair and repeat-read. Permit read-only verification recovery.
- Enrollment/Auth: reuse strict existing Google owner ID-token validator and nonce challenge pattern; configured identity/capability mandatory, device UUID-bound 300s single-use nonce, active UUID replacement denied, shared token mint/hash helper preserves legacy pairing behavior. No Session effective-user authorization.
- Android: Google consent requests existing server audience and server nonce; token sent directly to same allowlisted backend, returned device token Keystore-encrypted then signed runtime readback. Recovery fields are optional advanced controls. Reuse signed-v1 and Keystore-encrypted token, same application identity/default signing semantics. Store accepted task ID for restart/manual refresh; same-objective pending submit reuses clientTaskId after response loss; composer released after wait. No voice promise.

## Verification available

`node tests/google-plugin.test.cjs` also runs the retained runtime/enrollment suite. It exercises actual native Gemini->Runtime->Google read->repeat-read->owner evidence, counts/header/Drive results, signed manager/device/replay/cross-owner denial, missing/null grants and API principal binding, spoofed URLs/callbacks, 401/403/500/malformed JSON, fixed endpoint/no-q/no-body/no-write/nonGoogle constraints, and zero Composio requests for native Google tasks. `node tests/runtime.test.cjs` uses exact repository SignedAuth, StateStore, GoogleIdentity and Utils baseline fixtures plus candidate Code/Runtime/Provider/Composio/Auth/Enrollment. It exercises real intake/replay/idempotency/state transitions/provider parser and wrong-owner/nonce/audience/issuer/expiry/verified-email/config/capability/device/challenge replay/conflict denials, plus fresh owner enrollment -> signed runtime and no tokens in logs; service transports and Google sheets are synthetic. No API spend or private mailbox data. Integration test results do not prove a physical Redmi endpoint.

Branch-only workflow `.github/workflows/icarus-prototype-candidate.yml` runs tests and assembles release UNSIGNED inspection APK. No API secrets, deployment or installation. Stable Android 36/dependency versions are reused from the existing successful build lane. Retained signing-key availability is UNKNOWN. Root inspected the original September22 release archive (SHA256 7ae0a7f9675ba25704d484ac47ec0c83a109944cf9061e1ec5b9c9e927b03c3f;77 entries): it contained no APK/keystore/JKS/p12/pfx/pem/key or signing-named file. That is evidence about this archive only, not global absence. An unsigned artifact is not install-ready and cannot establish patch compatibility.

## Unresolved acceptance boundaries

1. Same-project Google deployment authority: existing OAuth relay timed out; do not replay it unchanged. Update existing deployment only after fresh source/rollback readback and authorized owner-local session.
2. Effective `provider.reason`, `PROVIDER_MODE=GEMINI_DIRECT`, Gemini free-billing/quota, require fresh private live verification before canary. Native Google tasks need no Composio key/config/connection. Existing Composio paths remain separate. No blanket enablement.
3. Fresh no-manual-code enrollment is implemented in candidate source only, not deployed or physically proven. Existing configured GOOGLE_OAUTH_CLIENT_ID/OWNER_GOOGLE_EMAIL_SHA256 and effective owner.google_identity capability must be read back privately. Android OAuth client for the retained package/signing fingerprint must already be accepted by the same Google project; CredentialManager consent must succeed on the actual Redmi. No API key/Google token/device token is embedded. Public same-deployment URL is prefilled. Legacy pairing stays available but is not the normal install flow.
4. Source manifest preserves existing scopes and adds `https://www.googleapis.com/auth/gmail.metadata` and `https://www.googleapis.com/auth/drive.metadata.readonly`. These are SOURCE ONLY. The same Apps Script deploying Google owner must authorize them; Android identity sign-in grants neither. Native API principal must equal the configured Michael owner. Gmail/Drive APIs and applicable Google project OAuth consent must be enabled/accepted by that owner; HTTP403 is an explicit permission gate, not proof of the precise cause. Anonymous webapp executes as deployer, so arbitrary users/data are unsupported. Background triggers cannot prompt for missing scopes; task status carries the gate, Connections opens only a native provided URL, refresh rechecks actual server grants/principal. If native URL is null/denied, owner must authorize through the existing Apps Script project; no invented auth link.
5. Retained Android signing key and installed identity must be verified before producing an installable patch; this candidate does not generate a new signing identity.
6. One fresh Redmi-origin native Google task with PC/Codex/ADB absent must reach Gemini, direct Google and same-task phone result, then match independent Gmail/Drive read and Michael verification. No PASS from this worker.

Known further runtime limitation: Apps Script one-shot trigger timing is not guaranteed to fit the Android 60-second polling window; saved-task refresh supports later readback. Scheduler installation/permission must be physically verified at deployment.

## Official contracts used

- https://developers.google.com/apps-script/reference/script/authorization-info
- https://developers.google.com/apps-script/reference/script/script-app
- https://developers.google.com/apps-script/guides/web
- https://developers.google.com/workspace/gmail/api/reference/rest/v1/users/getProfile
- https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list (gmail.metadata forbids q)
- https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get (format metadata, specified headers)
- https://developers.google.com/workspace/drive/api/reference/rest/v3/about/get
- https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list

Google-managed authorization is the backend deploying owner’s authorization; the ID token establishes the configured request owner, not API permission. No live consent, provider execution, deployment or signing performed by this source unit.
