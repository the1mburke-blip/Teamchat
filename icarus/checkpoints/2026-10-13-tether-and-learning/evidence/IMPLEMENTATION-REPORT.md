# ICARUS mobile Tether model selector — 12 October 2026

**Source implemented and locally tested. Live mobile completion remains unverified.**

The actual previously modified source was found at `C:/Users/the1m/OneDrive/Desktop/dsh-tether-source/dsh-tether-0.1.20`. Its existing modification against the downloaded upstream ZIP was `host/src/main.rs`; the ICARUS memory/identity documents and ten skills were present as additional files. The tested selector changes have been written back to that source. Nine changed/new files were read back and matched the tested output hashes. Protected identity, memory, skill, permission, capability and Rust files remain unchanged. Neither live PC nor phone installation was replaced.

The update provides provider/model selection, including configured local models; model and shared-provider quota observations; RPM/RPD/TPM and provider-specific dimensions when exposed; rate-limit status; live reset/retry/local-cooldown countdowns; literal `unknown` for unavailable data; and optional admitted zero-cost fallback. OpenRouter's read-only quota API is supported through an existing credential reference. No provider API reader or automatic fallback is enabled in the delivered defaults.

**Evidence:** 22 tests passed. An isolated context using installed Cordis 4.0.4 / DSH 0.2.0-rc.2 loaded the actual modified Tether plugin and exercised real localhost 429 header capture, fallback routing and exhaustion. The delivered browser client was tested with synthetic data at desktop and 390×844 phone dimensions: search, local model selection, decreasing countdowns and explicit unavailable-API reporting worked. No browser console errors were observed. The screenshot is a labelled test fixture, not a phone screenshot or live quota reading.

**Exact blockers:** no Rust cargo/rustc in PATH or standard toolchain locations; the source lacks the bundled `app/src-tauri/android-runtime` assets; detected PATH Java is JDK 17 while the build requires JDK 21; no adb/device test route was available in this task; no live provider credentials/quota API, zero-cost model eligibility, local inference server or physical-phone behavior was verified. An SDK using another HTTP transport or discarding headers/structured metadata may expose only unknown quota details. Independent code review and final phone readback remain outstanding. No APK was built, installed or published.

**Cost and governance:** €0 new spending, zero external provider inference/API calls, no purchases or subscription changes; chat allowance unmeasured. Codex implemented the source; local Node and installed-library contexts executed the checks. No named Claude/DeepSeek executor or independent reviewer was invoked. Relevant governance, preflight, routing, blocker, verification and handoff instructions were read. Completion is not self-certified as PASS.

**Patch delivery correction:** the requested deliverable is a plugin/source patch. `ICARUS-DSH-Tether-v0.1.20-patch.zip` contains only nine changed/new files, a unified patch and before/after hashes. The patch applied to an isolated copy of the actual starting source; every changed file matched the tested output byte-for-byte, and all other existing files remained unchanged. Windows Git line-ending conversion was explicitly disabled for that check. The archive payload hashes were read back. No additional feature tests or live installation changes were performed in this packaging step.

**Next admissible step:** inspect the existing installation's loaded plugin and apply the JavaScript patch through verified filesystem access, then restart DSH/reload the interface and verify the loaded files and unchanged identity/permissions. A native APK rebuild is not inherently required by these JavaScript changes. In remote phone mode, the target is the connected host's plugin. In built-in phone local mode, inspected `app/src-tauri/src/local.rs` copies the plugin from the private runtime skeleton into DSH_HOME on every start; both copies must be addressed, preserving the existing runtime manifest so it does not trigger extraction from the APK. Access to those private phone files and a safe device patch route have not been established. Build-toolchain limitations above apply only if an APK build route is chosen; they are not established blockers to a filesystem plugin patch. See `README-PATCH.md` and `patch-evidence.json` for the verified source-patch procedure and exact remaining limits.

Evidence files shipped beside the source:

- `test-results.txt`: final 22-test run.
- `runtime-evidence.json`: isolated installed-library runtime check; one localhost HTTP call, zero provider calls.
- `source-evidence.json`: baseline/upstream comparison and protected-file hashes.
- `source-writeback.json`: actual Desktop source writeback and matching hashes.
- `mobile-selector-fixture.png`: real delivered client rendered with synthetic quota data.
- `icarus-dsh-tether-0.1.20/MODEL-SELECTOR.md`: scope, configuration, behavior, limitations and primary references.

The known unsuccessful routes were an initial sandbox-denied loopback connection (resolved through an approved localhost-only test run), an Electron Node-mode source inspection without readback (replaced by read-only ASAR extraction), and a Cordis injection callback returning an invalid effect (fixed and verified in the installed-library context). No live app or credential store was changed during those checks.
