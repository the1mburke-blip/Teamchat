# ICARUS Android — Hermes-body source stage (8 October 2026)

**State: STAGED SOURCE / NOT COMPILED / NOT INSTALLED / NOT VERIFIED ON REDMI.** Michael requested a single Icarus-branded Android body keeping Hermes's useful runtime and Qwen, with Icarus's identity as the primary persona and policy authority.

## Proven inputs
- Standalone donor: https://github.com/l3ad3r1/Hermes-Agent-Android ; MIT license. Shared core: https://github.com/l3ad3r1/agent-core . Current donor `agent-core.ref`: `8445f2a04d4f9ca48c7c8d12221ad33064dd1b45`.
- Icarus baseline: this repository PR #78 (Hermes mobile foundation, inert), PR #63 (governance-kernel candidate, not deployed); neither grants live mobile authority.
- Identity artwork: Michael's approved **Celestial Gold Winged Emblem.png**, 7 Oct 2026; binary SHA256 `b55af87a4934fcef76a7a16003dd7406b9558a120a97e918485494f151d86b89`. The original image lives in Michael's ChatGPT Library; it is **not** in GitHub. Transfer only via authorized asset handling.
- Current Android provider and Qwen settings, Gemini/OpenRouter keys, and ChatGPT failsafe are NOT migrated automatically or hard-coded.

## Staging implementation
- Keep Hermes Kotlin class names, source license, core tool interfaces and on-device model runtime; do NOT concatenate two runtimes.
- Replace visible app string values with Icarus and launcher raster/adaptive icon with the **exact approved asset**. Candidate applicationId `com.icarus.preproduction` keeps installed Hermes intact and avoids hijacking its signing identity.
- Inject Icarus's continuity/persona prefix at the actual `OrchestratorImpl.kt` stable-system-prompt seam. Prompt is guidance only, not permission.
- Put a deterministic **DENY** stop-gate before two standard interactive tool-call lanes (`OrchestratorImpl.kt` and `AgentLoopRunner.kt`). These are fail-closed scaffolds, **not a complete tool gateway**. Do not enable tools until the real Icarus policy/permit authority and all alternative entrypoints (direct, API, background, plugin/MCP, accessibility, voice) have been covered and independently verified.
- Preserve memory files and models; ancestral memory may be read only from an authenticated and verified Icarus lineage snapshot. Do not invent or overwrite memory.
- `apply_icarus_overlay.py` is a *staging patch* to apply within a donor checkout with the approved logo passed separately. It must fail if upstream anchors drift. Do not stage secrets or signing identities.

## Acceptance / STOP
A source-overlay claim requires exact GitHub readback and static checks. **APK claim** requires real CI/Gradle logs and APK SHA, package/signature validation. **Icarus authority claim** requires adversarial deny/replay/self-PASS tests plus bypass audit. **Mobile claim** requires separate physical Redmi evidence for standalone Qwen, no desktop URL, correct launcher, memory lineage, permissions and tool gates.

Any successful build at this early stage is **inspection-only** and NOT authorization to install or operate a production agent. Unverified native/remote/bot paths must remain disabled in the final mobile artifact.

Protected: Teamchat main, PR #63/#78, production Apps Script/Shopify/Make/Buffer/Metricool/Publora, installed phone, credential stores. €0 only. No signed APK, paid service, deployment or owner authorization assumed.

**PRE-FLIGHT:** Owner Michael; orchestration ChatGPT; repository staging via deterministic GitHub connector; no authenticated Codex/Claude worker acceptance observed; allowance unknown. `TRAINING_MATRIX.md` HV-EXP-001: "A strong model without the required read/write/verification capability is the wrong execution chair. Capability-gate the entire route before spending execution attempts." This stage is bounded by its actual file-edit capability. Independent compiler/device evidence not yet available.

## Relocated canonical lineage input (10 October 2026)
The staged build now consumes the four canonical files from
`drafts/icarus/2026-10-10-dsh-tether-rebrand/source/icarus/memory/` on
`feature/icarus-dsh-tether-rebrand-20261010`. A deterministic authenticated
GitHub Actions runner checks byte equality against the pinned relocated ICARUS source commit
and records the exact source commit and SHA256 values in `lineage-source/`.

Invoke the existing overlay against the **real Hermes Android checkout** with
`--lineage-root drafts/icarus/2026-10-08-hermes-shell/lineage-source`
and the same `--hermes-checkout` / `--approved-logo` arguments as before.
The overlay copies exactly identity.md, inherited.md, learned.md, current-state.md
into `app/src/main/assets/icarus/memory/` with an immediate hash readback.
`AGENTS.md` is DSH workspace guidance and is deliberately not an Android
authority source. No paid services, credentials, production writes, or alternate
mobile donor have been introduced. This is SOURCE STAGING, NOT an APK or
runtime memory-load proof.

## Installed Hermes compatibility correction — 10 October 2026
This isolated branch targets the **already-installed standalone Hermes Android app**.
A previous diagnostic staging build changed package ID to com.icarus.preproduction
and its manifest Tinker Application class. Those are NOT in-place updates.
The corrected staged overlay preserves the donor package com.hermes.agent,
the existing AndroidManifest and the HermesTinkerApplication loader, and
injects ICARUS bootstrap into the existing patchable HermesApplicationLike
before the Hermes execution worker starts. Central deny-first gate remains
partial, not a completed permit system.

**Delivery hard gates:** Real installed version, package, TINKER_ID and
certificate must match a source release with an archived base. Tinker patch
requires original release signing key; debug builds from GitHub cannot update
a release-signed application. We do not copy the original key, publish to
the donor's release, change installed app or ship a diagnostic APK.
ICARUS authority bypass testing, patch build and physical phone confirmation
are separate acceptance gates.
