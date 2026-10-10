#!/usr/bin/env python3
"""Graft an ICARUS-owned Android entrypoint, lineage and central tool gate onto
the already staged Hermes donor. This changes authority placement, not branding.
Run only AFTER apply_icarus_overlay.py against the pinned donor and engine.
"""
from pathlib import Path
import argparse
import hashlib


def once(path: Path, old: str, new: str):
    content = path.read_text(encoding="utf-8")
    if content.count(old) != 1:
        raise RuntimeError(f"ICARUS supervisor anchor mismatch: {path.name} has {content.count(old)} copies of {old[:75]!r}")
    path.write_text(content.replace(old, new), encoding="utf-8")


def install(donor: Path, lineage: Path):
    app = donor / "app"
    engine = donor / "agent-core"
    if not (donor / ".git").exists() or not (engine / ".git").exists():
        raise RuntimeError("Original pinned Android and agent-core checkouts are required")
    files = ("identity.md", "inherited.md", "learned.md", "current-state.md")
    for name in files:
        f = lineage / name
        bundled = app / "src/main/assets/icarus/memory" / name
        if not f.is_file() or not bundled.is_file() or not f.read_bytes().strip():
            raise RuntimeError("Missing staged inherited lineage " + name)
        if f.read_bytes() != bundled.read_bytes():
            raise RuntimeError("ICARUS memory not byte-identical: " + name)

    # Android OS entrypoint: ICARUS Tinker shell -> ICARUS patched delegate -> Hermes worker.
    manifest = app / "src/main/AndroidManifest.xml"
    once(manifest,
         'android:name=".tinker.loader.HermesTinkerApplication"',
         'android:name=".tinker.loader.IcarusTinkerApplication"')
    loader = app / "src/main/java/com/hermes/agent/tinker/loader/HermesTinkerApplication.java"
    body = loader.read_text(encoding="utf-8")
    if "public final class HermesTinkerApplication" not in body:
        raise RuntimeError("Tinker shell changed upstream")
    out_loader = loader.with_name("IcarusTinkerApplication.java")
    if out_loader.exists():
        raise RuntimeError("ICARUS shell already exists, refusing double install")
    revised = body.replace("HermesTinkerApplication", "IcarusTinkerApplication").replace(
        '"com.hermes.agent.tinker.HermesApplicationLike"',
        '"com.hermes.agent.tinker.IcarusApplicationLike"')
    out_loader.write_text(revised, encoding="utf-8")

    delegate = app / "src/main/kotlin/com/hermes/agent/tinker/HermesApplicationLike.kt"
    original = delegate.read_text(encoding="utf-8")
    if "com.hermes.agent.data.agent.IcarusLineage.loadAtStartup(application)" not in original:
        raise RuntimeError("Missing previous staged memory startup")
    migrated = original.replace("HermesApplicationLike", "IcarusApplicationLike")
    migrated = migrated.replace("HermesTinkerApplication", "IcarusTinkerApplication")
    migrated = migrated.replace(
        "        HermesTinker.install(this)",
        "        HermesTinker.install(this)\n"
        "        // ICARUS is bootstrapped before content providers and Hilt consumers run.\n"
        "        if (!ShareTinkerInternals.isInPatchProcess(app)) {\n"
        "            com.hermes.agent.data.tool.IcarusAuthority.bootstrap(app)\n"
        "        }")
    migrated = migrated.replace(
        "        com.hermes.agent.data.agent.IcarusLineage.loadAtStartup(application)\n", "")
    migrated = migrated.replace(
        "        HermesAppStartup.start(application)",
        "        com.hermes.agent.data.tool.IcarusAuthority.requireReady()\n"
        "        // Hermes is a subordinate execution body; no unverified lineage may start it.\n"
        "        HermesAppStartup.start(application)")
    out_delegate = delegate.with_name("IcarusApplicationLike.kt")
    if out_delegate.exists():
        raise RuntimeError("ICARUS startup delegate already exists")
    out_delegate.write_text(migrated, encoding="utf-8")

    proguard = app / "proguard-rules.pro"
    value = proguard.read_text(encoding="utf-8")
    value += "\n# New ICARUS outer ApplicationLike is constructed by Tinker reflection.\n"
    value += "-keep class com.hermes.agent.tinker.IcarusApplicationLike { public <init>(...); }\n"
    proguard.write_text(value, encoding="utf-8")

    # The owner control code is compiled into the shared core: the Hermes model
    # cannot become the authorization decision-maker just by writing a prompt.
    tool_dir = engine / "core/tools/src/main/kotlin/com/hermes/agent/data/tool"
    if not tool_dir.is_dir():
        raise RuntimeError("Pinned shared ToolCallExecutor module missing")
    expected = ",\n".join(
        '        "' + name + '" to "' + hashlib.sha256((lineage / name).read_bytes()).hexdigest() + '"'
        for name in files
    )
    authority = r'''package com.hermes.agent.data.tool

import android.content.Context
import java.security.MessageDigest

/**
 * ICARUS owner-side boot and authorization boundary.
 * Boots from Android Application attach before the Hermes worker initializes.
 * Donor model prompts, plugins and retrieved text may not modify this table.
 * All unknown actions DENY. No model-supplied PASS or tools can mint a permit.
 *
 * LIMIT: direct calls to raw capabilities outside ToolCallExecutor are not yet
 * covered. This is a bounded owner-side gate, not complete sandbox isolation.
 */
object IcarusAuthority {
    private val expected = linkedMapOf(
__EXPECTED__
    )
    private val readOnlyTools = setOf(
        "get_current_datetime", "get_current_time", "get_weather", "weather",
        "web_search", "web_fetch", "memory_search", "search_memory", "memory",
        "search_conversations", "search_sessions", "list_bots"
    )
    @Volatile private var snapshot: Map<String, String>? = null

    @Synchronized
    fun bootstrap(context: Context) {
        if (snapshot != null) return
        val verified = linkedMapOf<String, String>()
        for ((name, digest) in expected) {
            val raw = context.assets.open("icarus/memory/" + name).use { it.readBytes() }
            check(raw.isNotEmpty()) { "ICARUS memory missing: " + name }
            val actual = MessageDigest.getInstance("SHA-256")
                .digest(raw).joinToString("") { "%02x".format(it) }
            check(actual == digest) { "ICARUS memory integrity violation: " + name }
            val text = raw.toString(Charsets.UTF_8)
            check(text.isNotBlank()) { "ICARUS memory blank: " + name }
            verified[name] = text
        }
        check(verified.size == 4) { "ICARUS lineage incomplete" }
        snapshot = verified.toMap()
    }

    fun requireReady() {
        check(snapshot?.size == 4) { "ICARUS CONTROL NOT BOOTSTRAPPED" }
    }

    /** Verifiable memory owned and read by ICARUS, separate from Hermes Room. */
    fun promptContext(): String {
        val verified = checkNotNull(snapshot) { "ICARUS lineage unavailable" }
        return verified.entries.joinToString("\n\n") {
            "[ICARUS INHERITED MEMORY: " + it.key + "]\n" + it.value
        }
    }

    /** Deterministic owner-controlled recall, bypasses provider hallucination. */
    fun memoryReport(): String {
        val verified = checkNotNull(snapshot) { "ICARUS lineage unavailable" }
        return "ICARUS verified inherited files (" + verified.size + "):\n\n" +
            verified.entries.joinToString("\n\n") { it.key + ":\n" + it.value }
    }

    fun isMemoryInspectionRequest(userMessage: String): Boolean {
        val q = userMessage.trim().lowercase()
        return q == "/icarus memory" || q == "icarus memory" ||
            q == "icarus memories" || q == "icarus memory report" ||
            q == "show your inherited memories" ||
            q == "list your inherited memories"
    }

    /**
     * Central fail-closed check for the known Hermes ToolCallExecutor path.
     * Only audited read-only names are eligible in this inspection build.
     * Owner-issued scoped permits for mutating actions are NOT implemented.
     */
    fun deniedReason(toolName: String): String? {
        if (snapshot == null) return "ICARUS_NOT_READY: worker cannot execute"
        if (toolName !in readOnlyTools) {
            return "ICARUS_PERMIT_REQUIRED: no owner-approved execution permit for " + toolName
        }
        return null
    }
}
'''.replace("__EXPECTED__", expected)
    (tool_dir / "IcarusAuthority.kt").write_text(authority, encoding="utf-8")

    executor = tool_dir / "ToolCallExecutor.kt"
    once(executor,
         '        val tool = registry.byName(call.name)',
         '        // ICARUS must authorize before any Hermes tool implementation is entered.\n'
         '        IcarusAuthority.deniedReason(call.name)?.let { return ToolResult.error(it) }\n'
         '        val tool = registry.byName(call.name)')

    module = app / "src/main/kotlin/com/hermes/agent/data/agent"
    orchestrator = module / "OrchestratorImpl.kt"
    once(orchestrator,
         'IcarusIdentity.ROOT + "\\n\\n" + IcarusLineage.promptPrefix() + "\\n\\n" + persona',
         'IcarusIdentity.ROOT + "\\n\\n" + ' +
         'com.hermes.agent.data.tool.IcarusAuthority.promptContext() + "\\n\\n" + ' +
         '"Hermes is an execution worker; ICARUS owns the policy and memory.\\n\\n" + persona')
    # Remove previously staged prompt-adjacent default deny; central executor owns it.
    once(orchestrator,
         '                    !IcarusExecutionGate.isAuthorized(deterministic.call.name) ->\n'
         '                        ToolResult.error("ICARUS_PERMIT_REQUIRED: action denied")\n', '')
    once(orchestrator,
         '    ): Flow<OrchestratorEvent> = channelFlow {\n',
         '    ): Flow<OrchestratorEvent> = channelFlow {\n'
         '        // ICARUS speaks for its own memory without relying on a model guess.\n'
         '        if (com.hermes.agent.data.tool.IcarusAuthority.isMemoryInspectionRequest(userMessage)) {\n'
         '            val report = com.hermes.agent.data.tool.IcarusAuthority.memoryReport()\n'
         '            send(OrchestratorEvent.ReplyToken(report))\n'
         '            send(OrchestratorEvent.ReplyComplete(report, AgentRole.CONVERSATIONAL, isOnDevice = true))\n'
         '            return@channelFlow\n'
         '        }\n')

    loop = module / "AgentLoopRunner.kt"
    once(loop,
         ' !IcarusExecutionGate.isAuthorized(gateName) -> '
         'ToolResult.error("ICARUS_PERMIT_REQUIRED: action denied")\n'
         '                    ', '')

    # Local source assertions: evidence of placement, NOT device/runtime proof.
    assert "IcarusApplicationLike" in out_loader.read_text()
    assert "IcarusAuthority.bootstrap(app)" in out_delegate.read_text()
    assert "IcarusAuthority.deniedReason(call.name)" in executor.read_text()
    assert "IcarusAuthority.memoryReport()" in orchestrator.read_text()
    print("ICARUS_SUPERVISOR_SOURCE_INSTALLED; memory SHA pinned; central tools fail closed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-checkout", required=True)
    parser.add_argument("--lineage-root", required=True)
    args = parser.parse_args()
    install(Path(args.hermes_checkout), Path(args.lineage_root))
