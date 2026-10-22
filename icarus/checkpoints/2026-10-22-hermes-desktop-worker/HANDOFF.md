# Hermes desktop worker refinement — 2026-10-22

## Provenance
Owner requested: refine the Python desktop helper for autonomous work and use the editable Hermes source where available. Executed in the Windows DeepSeek Harness workspace by the active ICARUS worker. External spend: EUR 0.

## Source preflight
The editable Hermes checkout was inspected at `Documents/Codex/ICARUS-Hermes/source`.
- `source/tools/computer_use_tool.py` registers the consolidated `computer_use` tool.
- `source/tools/computer_use/schema.py` defines the action vocabulary and recommends capture/element targeting over raw pixels.
- `source/tools/computer_use/tool.py` and `cua_backend_input.py` contain approval, sticky-target, delivery, and escalation patterns.
- The editable checkout is not proven to be the packaged live Harness GUI source.

## Implemented change
`OneDrive/Desktop/desktop_input.py` is version 2.1.0. It retains the bounded Windows ctypes worker and now performs discovery-only loading of Hermes `tools.computer_use.schema` when the checkout exists. Its JSONL handshake reports the source path, tool name, and discovered Hermes actions. Hermes `capture` is accepted as an alias for the worker's bounded screenshot operation; local dry-run and approval gates remain authoritative. No Hermes runtime state, credentials, or protected files are imported.

The worker also provides persistent JSONL request IDs/sequences, duplicate rejection, a single-instance mutex, action locking, dry-run default, explicit mutation approval, foreground identity checks, DPI/virtual-desktop mapping, deadlines/budgets, atomic screenshot output roots, hashes, structured delivery/verification results, and fail-stop errors.

## Verification evidence
- Python compilation passed.
- JSONL handshake passed and reported `hermes_source.available: true`, `tool: computer_use`, source `C:\Users\the1m\Documents\Codex\ICARUS-Hermes\source`, and the exact Hermes action list.
- Hermes-style dry-run `capture` request passed without writing a file or injecting input.
- Earlier safe worker tests passed: ping, dry-run mutation plan, duplicate request rejection, click-approval rejection, and bounded temporary screenshot capture with independent cleanup.
- A direct Hermes cua-driver contract probe was attempted read-only. It did not establish driver readiness because the bundled Python environment lacks the Hermes dependency `ruamel` (`ModuleNotFoundError`); no installation or retry was performed.

## Boundaries
Full Hermes cua-driver/AX semantic control is not claimed: driver readiness, package linkage to the live GUI, element discovery, and semantic postconditions remain unverified. Raw-coordinate fallback remains guarded and caller-verified. No credentials, private transcripts, provider call, network spend, protected-policy edit, or installed app archive mutation occurred.

## Status
**Verified schema reuse and local worker compatibility. Full semantic Hermes computer-use backend: FAIL/unverified pending dependency-complete, authorized runtime linkage and independent live acceptance.**
