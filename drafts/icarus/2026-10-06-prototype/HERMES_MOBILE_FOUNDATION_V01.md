# Hermes Mobile Foundation V01

## Purpose
Provide a minimal, inert scaffold that defines the contract between Icarus (policy authority) and a future Hermes executor on mobile devices. The scaffold is deliberately disabled and contains no credential material or authority‑granting logic.

## Integration Sequence (future)
1. Icarus loads `HermesExecutorAdapter.gs` in the Apps Script runtime.
2. Icarus enables the adapter via `HermesExecutorAdapter.setEnabled(true)` only after policy verification.
3. Android client implements `HermesExecutorContract.Executor` using the Kotlin contract.
4. Icarus sends a `Request` (capability + payload) to the Android side through `AppsScriptGateway`.
5. Android side returns a `Response` (`Denied` or `Accepted`) to Icarus.
6. Icarus adjudicates the response according to its evidence and permit rules.

## Non‑Goals
- No actual network communication.
- No execution of external tools or scripts.
- No credential handling or storage.
- No PASS/ALLOW semantics; only explicit `DENIED` responses are defined.

## Acceptance Gates (future)
- **Gate 1 – Inertness**: The adapter must return `DENIED` for any request when disabled.
- **Gate 2 – No Credential Leakage**: Source files contain no strings that resemble keys, tokens, or credential identifiers.
- **Gate 3 – Policy Boundary**: All decision‑making remains in Icarus; the executor only returns data.
- **Gate 4 – Test Coverage**: Node test `hermes-foundation.test.cjs` passes without external dependencies.

## Future Work
- Implement a concrete `Executor` on Android that respects the contract.
- Add capability whitelist and safe sandboxing.
- Integrate with Icarus adjudication pipeline.
