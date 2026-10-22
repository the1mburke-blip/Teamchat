# Autonomous desktop worker test — 2026-10-22

## Provenance
Owner requested: “test your new skill.” Executed in the Windows DeepSeek Harness workspace against `OneDrive/Desktop/desktop_input.py`, using the bundled Python runtime. External spend: EUR 0.

## Tests
1. Python compilation passed.
2. Persistent JSONL `serve` handshake and `ping` passed. The handshake reported protocol `desktop-input-jsonl-v2`, version `2.1.0`, per-monitor-v2 DPI, 1920×1080 virtual desktop/capture dimensions, and Hermes schema discovery available.
3. Hermes-compatible dry-run `capture` passed; the planned `not-written.png` path was independently checked and no file existed.
4. Dry-run click/type plan passed with zero click and typed-unit counts, so no mutation was delivered.
5. Non-dry-run click without policy approval was rejected with `CLICK_NOT_APPROVED_OR_BUDGETED`; counts remained zero.

## Boundaries
This test did not invoke click or type, did not install Hermes dependencies, and did not prove semantic AX/CUA behavior. It tests protocol, schema discovery, dry-run, and refusal gates only.

## Status
**Verified safe worker test for the exercised gates; full autonomous GUI semantic control remains unverified.**
