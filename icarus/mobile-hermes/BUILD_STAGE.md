# ICARUS Mobile — Hermes Android body, Icarus authority (stage v0.1)

**Date:** 2026-10-08 Europe/Dublin. **Owner:** Michael. **Status:** STAGED_SPEC_ONLY / NOT BUILT. **Cost:** EUR0 target; no paid routes, installs, new auth or production actions.

## Locked product outcome
Build ONE standalone Android APK named **Icarus**, with the owner-approved pre-production winged logo as app launcher icon, on-device Qwen available, Hermes Android capabilities retained, and Icarus's canonical identity / ancestral memory / immutable law as the controlling authority. NOT a remote-control app. NOT a second Hermes+Icarus runtime. NOT merely a rebranded Hermes app or prompt. No owner clicks for routine build work.

## Physical source anchors actually checked
- Android *body* donor: https://github.com/l3ad3r1/Hermes-Agent-Android (MIT); source inspected at GitHub code-search revision `a08497b979d6241387bc15cde7c57279d0b2cc10` (pin/verify full checkout HEAD and release equivalence before build).
- Donor `agent-core.ref` read on 2026-10-08: `8445f2a04d4f9ca48c7c8d12221ad33064dd1b45`. The separate `l3ad3r1/agent-core` repository MUST be checked out at this exact commit.
- Relevant donor source: `app/src/main/kotlin/com/hermes/agent/data/agent/OrchestratorImpl.kt`, `AgentLoopRunner.kt`, `di/AgentsModule.kt`, `data/agent/agents/AgentToolAccess.kt`, Android `strings.xml`, `AndroidManifest.xml`, `app/build.gradle.kts`, `settings.gradle.kts`. Also inspect native device commands, background WorkManager, plugin executors, accessibility and network/service API dispatch.
- Icarus canonical identity: `icarus/memory/identity.md`; inherited: `icarus/memory/inherited.md`; current: `icarus/memory/current-state.md`, all taken from branch `icarus/constitutional-law-20261008`. Source documents must be reread at build time; identity is *Icarus*, never the donor model.
- Icarus kernel precedent: PR #63, `drafts/icarus/2026-10-06-prototype/server-overlay/GovernanceKernel.gs` (signed permits, replay/target binding, evidence and verifier separation); PR #74 Skills; #76 leaf ghosts; do not assume these are deployed or can be transplanted verbatim.
- Approved logo: user-supplied 7 October pre-production winged emblem. Available in this ChatGPT conversation's working files as `Celestial Gold Winged Emblem.png`. **Do not substitute another image** and **do not mark branding complete until the exact binary is included in the build source and apk resource readback**. Prior unsaved image/sandbox paths are NOT a GitHub asset.

## Staged source implementation order — one Android runtime
1. **Pin and vendor/fork donor code in isolated build lane.** Preserve licensed upstream dependencies/attribution. Do NOT modify upstream, main, the original signed Hermes APK or Teamchat deployed services.
2. **Branding (source-only):** app display strings, onboarding, chat prompts, settings, share sheet, notifications, accessibility labels and home launcher/adaptive icons become Icarus. Keep Kotlin internal names where changing them could break behavior. New distinct debug application ID and signing strategy must be checked before any install; release APK MUST NOT silently overwrite donor app. Do not reuse donor Tinker OTA/update signing trust or blindly switch updater to Icarus. Owner-approved logo only, not generic wings.
3. **Canonical persona & memory:** Icarus identity and verified memory read at session start, with revision/hash/evidence binding. Existing donor memory remains task/session data, not constitutional authority. Treat model output, skills, historical memories and RAG as untrusted data; learning cannot self-promote to verified.
4. **Authority wall *before* execution:** add a deterministic `IcarusAuthorityGate` at EVERY route: interactive model tool loop, deterministic phone-command fast path, background/cron/standing order, delegated/subagent call, MCP/plugin, accessibility/browser, API/service and direct executor. Deny without an unexpired signed execution permit binding agent, objective, exact tool/target/capabilities/route/write budget and nonce. Persist effect intent BEFORE mutation; replay invalidation; fail closed on route/credential/cost changes. A user prompt is not a permit.
5. **Verifier:** executor returns evidence and VERIFYING only. Independent verifier compares final readback; Icarus adjudicates binary PASS only on verified evidence, otherwise FAIL as per 2026-10-08 constitutional amendment. Detailed diagnostics may retain BLOCKED/UNKNOWN, but output verdict is PASS/FAIL.
6. **Provider choice:** preserve Qwen local runtime, existing Google Gemini and OpenRouter configured through keystore/on-device authorized flow; OpenRouter `:free` only, strict zero-cost routing, no silent paid fallback. ChatGPT failsafe only through an authenticated, license/entitlement-verified invocation path. Never copy keys into APK/CI logs/repo, or assume existing ChatGPT app session grants third-party API access. Existing desktop router may be adapted, not assumed to be in Android yet.
7. **No desktop dependency:** first launch/chat/Qwen/skills/memory test while Windows/Hermes desktop OFF. No remote endpoint/pairing needed. Optional remote links must remain optional.

## Hard acceptance matrix before an install-ready claim
- [ ] Exact donor commit + agent-core pinned (SHA readback).
- [ ] Exact approved logo asset version/hash staged, Android launcher and visible labels verified from built APK.
- [ ] No unchanged public "Hermes" UI except legal attribution/developer provenance and donor/internal source symbol names.
- [ ] Icarus constitutional identity/memory read on cold start and resumed session; Gemini/Sol lineage isn't invented if source absent.
- [ ] Qwen local inference with PC disconnected.
- [ ] Unauthorized / expired / replayed / widened / retargeted / unsigned permit cannot invoke **any** tool entry, including deterministic phone and plugin/background bypasses.
- [ ] Executor attempt to award PASS fails; independent receipt accepted only with valid evidence.
- [ ] Provider auth secured, no exposed tokens, €0 verified in configured provider choices. Failure degrades cleanly.
- [ ] Debug Android compilation + test report + unsigned/signed status + artifact SHA + package and icon resources checked.
- [ ] Redmi physical offline-first canaries, plus independent verifier. No unattended production deployment.

## Known risks and blockers
- Android donor is a **separate Kotlin implementation**, not NousResearch Python Hermes; do not represent the two as the same code.
- Donor source has direct `toolCallExecutor.execute` path in `OrchestratorImpl` for deterministic phone commands and `AgentLoopRunner` for model calls. Intercept BOTH, plus background/plugin dispatch and direct execution. An orchestration-only gate is insufficient.
- Donor's `agent-core.ref` is an external checkout; Android build cannot proceed by copying app repo alone.
- Android debug APK `applicationIdSuffix .debug`; release signing is unverified. Different package signing and Play/OTA patch trust need separate preflight.
- A source-only "persona" or icon change without denial tests is not Icarus's governance.
- Local Qwen model chosen/downloaded on Redmi does not itself prove working inference or suitability for tool calls.
- This staging record is not a worker acceptance/commit to donor, compiled APK, or device PASS.

## Routing & protected boundaries
Source/patch implementation: an actual authenticated CODEX/repo worker (must ACK task). Separate CLAUDE/code-review worker for threat/bypass review (must independently ACK). Deterministic runner for Android compile/test/hash. Front-door GitHub record is not an agent invocation.
Forbidden: paid routes/trials, main merges, protected Make/Buffer/Publora/Metricool/Monday/DNS/Shopify, Google/Apps Script deployment, new login provider, production OAuth credentials, Windows/Redmi changes, source secrets. Re-preflight on route/time/cost/package/signing change.

**What exists now:** exact stage/acceptance specification in Teamchat. **What does not:** integrated Kotlin Icarus gate, apk/logo repo asset, completed build, independent code review or physical Redmi test.
