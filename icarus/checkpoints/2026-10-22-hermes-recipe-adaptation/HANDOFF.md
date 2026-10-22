# Hermes recipe adaptation — 2026-10-22

## Provenance
Owner asked whether the Hermes-based autonomous skill could be adapted using the recipe skill and requested that it be done now. Executed in the Windows DeepSeek Harness workspace at EUR 0 spend.

## Adaptation
Created the active recipe `hermes_desktop_preflight` in `C:\Users\the1m\Icarus-Harness\recipes`. It composes native `read`, `regex_extract`, and `join` steps to audit the local `desktop_input.py` against the editable Hermes `tools/computer_use/schema.py`. It reports the worker version, safety markers, and selected Hermes action names without invoking desktop input or modifying production state.

The first draft was rejected by the recipe loader because it exceeded the 12-step limit and attempted output variables not bound by accepted steps. The recipe was corrected to seven steps and reloaded successfully. This is a verified recipe-composer repair, not a claim that recipes can install Hermes dependencies or create a missing CUA driver.

## Verification
- `recipe_list` accepted `hermes_desktop_preflight(worker:string, hermes_schema:string)` as a seven-step recipe.
- `recipe_run` returned `worker_version=2.1.0`, worker safety markers including `hermes_schema_info`, `dry_run`, `CLICK_NOT_APPROVED_OR_BUDGETED`, and `OUTPUT_ROOT_REQUIRED`, and Hermes action names including `capture,click,type,set_value,wait`.
- Native Python compilation passed after the adaptation.
- A fresh JSONL worker handshake and `ping` passed afterward, reporting Hermes schema discovery available and protocol `desktop-input-jsonl-v2`.

## Boundary
The recipe is a static preflight/audit wrapper. Recipe composition cannot by itself install the missing Hermes `ruamel` dependency, verify `cua-driver`, link the editable checkout to packaged Harness, or prove AX semantic GUI behavior. No click or type was invoked, no credentials were read, and no external spend occurred.

## Status
**Verified recipe-based Hermes preflight and post-adaptation worker smoke test; full Hermes semantic backend remains FAIL/unverified.**
