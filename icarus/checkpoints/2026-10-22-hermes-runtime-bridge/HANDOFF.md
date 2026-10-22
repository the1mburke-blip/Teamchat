# Hermes runtime and live profile bridge handoff

Date: 2026-10-22 Europe/London
Provenance: Michael directed installation of the missing Hermes dependency, driver readiness verification, live Harness connection, and harmless screenshot capture. External spend: EUR 0.

## Verified

- Installed `ruamel.yaml==0.18.16` and `ruamel.yaml.clib==0.2.15` in the actual DSH primary Python runtime (`Python 3.12.14`).
- Installed the additional imports required to exercise the Hermes backend path: `requests==2.33.0`, `httpx[socks]==0.28.1`, `psutil==7.2.2`, and `mcp==2.0.0` with resolver dependencies.
- Hermes `cua_driver_runtime_contract_status()` returned `ready: true` for `cua-driver-0.21.0-win32-x64`, version `0.21.0`, with an empty reason.
- A direct `cua-driver mcp --direct --no-overlay` MCP session initialized and `get_desktop_state` returned a 1920x1080 screenshot.
- The DSH Hermes bridge returned and saved `C:\Users\the1m\OneDrive\Desktop\hermes-captures\hermes-capture-219d2e0b4ab44213.png` (456295 bytes; SHA-256 `219d2e0b4ab44213ebeb687f672a6eaa3f58d25d717802a8a759c4662890c053`). Independent image readback confirmed PNG dimensions 1920x1080 and the screenshot showed the live Harness window.
- Added linked package `@deepseek-ai/dsh-hermes-computer-use` to the live desktop profile, installed the profile lockfile with bundled pnpm, verified it in the dependency graph, and restarted the existing Harness host. The bridge exposes only `action=capture`; no click/type/mutation is registered.

## Boundary

The high-level Hermes `handle_computer_use` wrapper still fails outside a trusted Hermes agent turn because its ICARUS authority scope is absent and the governed sandbox backend requires Docker (`AuthorityDenied: ICARUS runtime authority missing`; Docker command unavailable). The direct capture bridge proves the installed Hermes cua-driver backend and live-profile package path, but a model-issued governed `computer_use` turn through the DSH UI was not independently observed.

Status: **Verified dependency installation, cua-driver readiness, direct harmless capture, profile linkage, and host restart; full governed Hermes computer-use invocation through the live Harness remains FAIL/unverified.**
