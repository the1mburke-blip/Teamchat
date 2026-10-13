# ICARUS model selector — implementation scope and status

12 October 2026, Europe/London. Owner: Michael. Implementation: Codex; tests: local Node and extracted installed DSH libraries. Independent reviewer: none. Status: source implemented and locally tested; live mobile endpoint remains unverified. No provider inference calls, purchases or new subscriptions were used. Chat allowance is unmeasured.

## Actual source inspected

The starting tree was `C:/Users/the1m/OneDrive/Desktop/dsh-tether-source/dsh-tether-0.1.20`, not a new upstream download. It contains the five canonical ICARUS documents and ten skill files. The inspected `host/src/main.rs` has `default_value = "never"` on the **phone simulator's approval reply policy**. This does not establish a global approval bypass. That file and every identity, memory, skill, capability and Rust source file are preserved unchanged.

Tether transports the DSH web interface; the model call and selection hooks belong to DSH. The inspected installed desktop DSH is 0.2.0-rc.2 with Cordis 4.0.4, matching the DSH version pinned for the Android bundle. The separate existing `icarus-quota-failover` plugin was inspected but not changed. Its configured cooldowns are retry policy, not provider reset facts.

## Delivered behavior

- `/models` opens a searchable provider/model selector in DSH's command menu. It uses the existing session model directory and `directory.select`, including registered local/OpenAI-compatible routes. Changing a model retains the session and uses the harness's normal model-selection procedure.
- The panel displays separate observations for each provider/model and provider-shared quota: quota hit, rate-limit status, RPM/RPD/TPM, exposed remaining/limit counts, reset countdowns, and a separately labelled local cooldown. Anthropic ITPM/OTPM and generic unknown-dimension requests/tokens are shown separately. Unknown fields literally display `unknown`.
- Undici diagnostic channels capture headers inside the exact `llm/stream` asynchronous scope. No global fetch replacement, response-body consumption, credential logging or message modifications are introduced. Streams close their original iterator on cancellation.
- Both successes and failures can supply headers. Structured Google RetryInfo/QuotaFailure, normalized quota/rate-limit errors, HTTP Retry-After seconds/date, Groq/OpenAI duration resets, Anthropic timestamps and OpenRouter epoch resets are handled. No reset is inferred from a public plan table, assumed daily boundary or local cooldown.
- Refresh status reads existing observations and the registered model catalog. Refresh provider APIs explicitly reads configured OpenRouter `GET /api/v1/key` using an existing credential reference. It reads exposed free-model daily request counts and credit/budget fields separately. The deprecated OpenRouter `rate_limit` object is ignored. No background polling, model inference, top-up or purchase occurs.
- Automatic fallback is off by default. It requires an explicit ordered list of admitted zero-cost and compatible routes; rejects paid/unapproved/duplicate routes; checks adapter context windows and input modalities; preserves the same agent/session; clears model-specific tuning on a route change; respects reported retry and exhausted-metric deadlines and local cooldowns; stops on exhaustion. An unknown quota reset keeps the exhausted route excluded until fresh evidence is available. A zero countdown does not assert renewed availability.
- The npm package includes the new client/server modules and canonical ICARUS source documents. Android runtime assembly includes the modules and a plugin-source SHA-256 in its manifest, so a same-version APK rebuild refreshes the bundled plugin. Existing Rust code preserves the separate DSH_HOME profile/settings during runtime replacement.

## Optional fallback and quota API configuration

Under the existing `dsh-tether` composition entry, keep `sidecar` and unrelated configuration intact, and add `modelSelector`. Leave `autoFallback: false` until real route cost, credentials, compatibility and loading are independently confirmed. The following is a schema example, not a live approved configuration:

```yaml
modelSelector:
  autoFallback: false
  localCooldownMs: 60000
  routes: []
  providerApis: []
```

Each fallback route needs exact registered `provider`/`model` IDs, `approved: true`, `costPolicy: verified-zero-cost`, and `compatibilityVerified: true`. Those flags record an admission decision; they do not prove pricing, hardware availability or tool support. The runtime additionally checks context-window and modality compatibility. Local models must already have a configured adapter and saved model entry; this feature does not download models or install an inference server.

An optional OpenRouter quota reader has `kind: openrouter-key`, the registered provider ID, and `credentialRef` equal to an existing credential-service reference. Do not put an API key in this config. No reader is enabled in the delivered defaults. The endpoint is fixed to `https://openrouter.ai/api/v1/key`; redirects are rejected.

Use one automatic router for a given agent scope. The existing separate quota-failover plugin may already be active on the PC. Enabling two routers together needs explicit reconciliation; this source update does not modify or disable the existing plugin.

## Evidence and exact limits

The accompanying test log records 22 passing tests, including real loopback HTTP headers, concurrent routing, unknown resets, provider-shared exhaustion, safe fallback, cancellation, model compatibility, native client module loading and same-version Android manifest refresh. `runtime-evidence.json` records an isolated check using the actual installed Cordis/DSH libraries: the modified Tether plugin loaded, observed a real localhost 429 despite a normalized UNKNOWN error, selected another provider, and stopped on exhaustion. This is not live provider inference.

The browser fixture used the actual delivered client with synthetic provider data. It demonstrated searchable local-model selection, live countdowns, explicit unknown fields and missing-API reporting at 390×844. `mobile-selector-fixture.png` is fixture evidence, not a phone screenshot. No browser console errors were observed in that check.

Exact blockers and remaining verification:

1. Rust `cargo`/`rustc` are unavailable in PATH; standard `.cargo/bin/cargo.exe` and `.rustup` are absent. No APK or Rust binary was compiled.
2. `app/src-tauri/android-runtime` is absent in the starting tree. A mobile build still needs the pinned runtime archive/dependency assembly, Android SDK/NDK, JDK 21 and Rust Android target. The detected PATH Java is JDK 17; other SDK/JDK installations were not fully audited.
3. No physical phone or connected `adb` was available through PATH for this task. Installation, WebView integration and on-device quota/fallback behavior remain untested.
4. No live model inference or account quota API was called. Live provider credentials/eligibility, actual zero-cost routes, local inference availability and provider API readback remain unverified. Canonical memory being present in a package does not prove it is loaded in a live session.
5. Header capture covers Undici transport. A provider SDK that suppresses headers, uses another transport, or discards structured error metadata can expose fewer facts. The display keeps them unknown. SDK-specific adapters would be needed to recover data those SDKs hide.
6. Quota observations and fallback exclusions are process-local and clear on restart. Historical observations are timestamped; elapsed resets remain historical evidence, not proof of availability. Independent code review and final phone readback are outstanding.

Next admissible action: build this exact source in an isolated Android lane with the required toolchain, then test the selector and fallback in a fresh ICARUS phone session while reading the loaded plugin/runtime fingerprints and unchanged identity/permission hashes. Do not publish an APK, change credentials, weaken permissions or enable paid fallback to resolve these blockers.

## Primary references checked

- [DSH agent events and request recovery](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/core/agent/README.md)
- [DSH agent loop](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/core/agent-loop/README.md)
- [Undici diagnostic channels](https://github.com/nodejs/undici/blob/main/docs/docs/api/DiagnosticsChannel.md)
- [Groq quota dimensions and headers](https://console.groq.com/docs/rate-limits)
- [Anthropic API rate limits](https://support.anthropic.com/en/articles/8243635-our-approach-to-api-rate-limits)
- [Gemini quota dimensions](https://ai.google.dev/gemini-api/docs/rate-limits)
- [OpenRouter quota/credit API](https://openrouter.ai/docs/api_reference/limits)
- [Ollama model catalog API](https://docs.ollama.com/api/tags)

The local installed library source, not the moving upstream documentation, determined the implemented hook and browser-module signatures.
