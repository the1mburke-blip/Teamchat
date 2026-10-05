# Icarus recovered live transport contract — sanitized

STATUS: LIVE V0.4 CONTRACT RECOVERED / DEVICE DATA REUSE STILL REQUIRED
DATE: 2026-10-05
COST: €0

## Direct source
Current Apps Script project exported read-only from Drive:
- Project: ICARUS NON_PROD Runtime SELF-CONFIG FINAL
- File ID: 14k-ImKDntPPXhhFC7Wzj-2nMEbRIxNxNBDFRtRt03Q-5E5132k7r-wGL
- Runtime: AS-0.4.0-composio-v31
- Relevant files: SignedAuth, Code, ComposioV31, Auth, OwnerVerification
- Current Control Plane shows Android device 6e3b87f4-e0b6-4f10-9ac0-64c36accad5f ACTIVE, app_build 0.4.0-composio-v31, last_seen 2026-10-05T22:42:48.936Z.

## Pairing
Pair remains an unsigned bootstrap request:
```json
{"op":"pair","deviceId":"<device>","pairingCode":"<one-time>","clientVersion":"<build>"}
```
Optional `googleIdToken` is accepted when configured.
Successful response data contains `deviceId`, plaintext `token` (returned once), `runtimeVersion`, `environment`, and Google-identity verification state.

Current server state has already consumed the one-time fallback pairing path. Do not assume a replacement package can pair again. Preserve/reuse the already-enrolled app data or prove a separately authorised enrollment path before device deployment.

## Signed v1 transport
All non-pair operations use a signed envelope. Plaintext-token submit/status requests are INVALID for v0.4.

Inner payload is a JSON string and MUST contain the same `deviceId`; it MUST NOT contain `token`.

Envelope:
```json
{
  "v": 1,
  "deviceId": "<device>",
  "timestamp": 0,
  "nonce": "<16-128 chars [A-Za-z0-9_-]>",
  "payload": "<exact inner JSON string>",
  "signature": "<64 lowercase hex chars>"
}
```

Constraints:
- timestamp is epoch milliseconds and must be within ±300000 ms.
- payload length <= 30000.
- nonce is single-use; replays are denied and persisted in ICARUS_REQUEST_NONCES.
- device must be ACTIVE.

Signing:
1. `tokenHashHex = lowercaseHex(SHA-256(plaintextDeviceToken))`.
2. `signingText = "ICARUS_QUEUE_V1\n" + deviceId + "\n" + timestamp + "\n" + nonce + "\n" + payload`.
3. `signature = lowercaseHex(HMAC-SHA256(key=UTF8(tokenHashHex), message=UTF8(signingText)))`.

## Operations
Submit inner payload:
```json
{"op":"submit","deviceId":"<device>","clientTaskId":"<uuid>","text":"<task>"}
```

Status:
```json
{"op":"status","deviceId":"<device>","taskId":"<task id>"}
```

Resume:
```json
{"op":"resume","deviceId":"<device>","taskId":"<task id>"}
```

Owner verification uses signed `owner_challenge` and `owner_verify` operations and Google owner identity. Do not bypass it.

## Response mapping
Envelope is `{"ok":true,"data":...}` or `{"ok":false,"error":"...","timestamp":"..."}`.

`taskForClient_` returns the persisted task plus:
- `evidence_fingerprint`
- `owner_verification`
- `auth_url` when needed
- `composio_tool` when present
- `composio_account_id` as evidence/state only
- parsed `result` when COMPOSIO_TASK_STATE.result_json exists

Core task fields include `task_id`, `status`, `objective`, and `evidence_ref`.

Do not send a Composio account selector in execution requests; prior live evidence showed that unsupported parameter caused HTTP 400.

## Live proof
Control Plane task ICT-9b8051e1-dc3c-4ebb-ac4d-98a494741bf0:
- source: Android device 6e3b87f4-e0b6-4f10-9ac0-64c36accad5f
- route: COMPOSIO_V31
- tool: GMAIL_FETCH_EMAILS
- persisted real Gmail result
- executor repeat-read matched
- owner verification persisted PASS at 2026-10-05T22:42:36.044Z
- final TASK_QUEUE status: PASS

## Integration boundary
Do not create a new backend, OAuth scheme, database, broker or provider.
Do not hard-code endpoint/token/pairing code.
Do not replace signed v1 with the archived plaintext-token contract.
Do not revoke or re-pair the current ACTIVE device merely to make the replacement shell work.

For the final Redmi build, safest route is an in-place update of the already-paired Android app using its existing package/signing identity and stored token, then wire the shell UI/gateway code into that app. A different package cannot read the current app's private token storage.

PASS remains: real Redmi task through this signed contract + independent result readback.
