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
    # CI produces a separately installable pre-production trial: each runner
    # uses a fresh debug signing key, so it cannot update the owner's existing
    # diagnostic package without wiping its app settings/keys. New package ID
    # preserves that install and its private data without requiring uninstall.
    isolated_id = "com.icarus.preproduction.control"
    once(app / "build.gradle.kts",
         'applicationId = "com.icarus.preproduction"',
         'applicationId = "' + isolated_id + '"')
    shortcuts = app / "src/main/res/xml/shortcuts.xml"
    old_pkg = 'android:targetPackage="com.icarus.preproduction"'
    contents = shortcuts.read_text(encoding="utf-8")
    if contents.count(old_pkg) != 4:
        raise RuntimeError("ICARUS launcher shortcuts expected exactly four package references")
    shortcuts.write_text(contents.replace(
        old_pkg, 'android:targetPackage="' + isolated_id + '"'), encoding="utf-8")

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
        "        val app = application",
        "        val app = application\n"
        "        // Bootstrap ICARUS BEFORE installing Hermes tooling or exposing the Hilt manager.\n"
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
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive

/**
 * ICARUS owner-side boot and authorization boundary.
 * Boots from Android Application attach before the Hermes worker initializes.
 * Donor model prompts, plugins and retrieved text may not modify this table.
 * All unapproved actions DENY. Only native owner confirmation can grant a one-use permit.
 *
 * LIMIT: direct calls to raw capabilities outside ToolCallExecutor are not yet
 * covered. This is a bounded owner-side gate, not complete sandbox isolation.
 */
object IcarusAuthority {
    private val expected = linkedMapOf(
__EXPECTED__
    )
    // Only explicit owner confirmation from the native UI issues a permit.
    // Permits are bound to exact tool arguments and consumed once.
    private val permits = mutableMapOf<String, Int>()
    private fun permitKey(name: String, args: Map<String, JsonElement>): String =
        name + "|" + kotlinx.serialization.json.JsonObject(args).toString()
    @Synchronized fun approveOwnerConfirmed(name: String, args: Map<String, JsonElement>) {
        requireReady()
        val k = permitKey(name, args)
        permits[k] = (permits[k] ?: 0) + 1
    }
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

    /** Hermes may not restore autonomous plugin, cron, backup or background jobs. */
    fun donorAutonomyPermitted(): Boolean = false

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
     * All tool actions require an exact, one-use, owner-approved permit.
     */
    @Synchronized
    fun deniedReason(toolName: String, arguments: Map<String, JsonElement> = emptyMap()): String? {
        if (snapshot == null) return "ICARUS_NOT_READY: worker cannot execute"
        val k = permitKey(toolName, arguments)
        val available = permits[k] ?: 0
        if (available > 0) {
            if (available == 1) permits.remove(k) else permits[k] = available - 1
            return null
        }
        return "ICARUS_PERMIT_REQUIRED: no owner-approved execution permit for " + toolName
    }
}
'''.replace("__EXPECTED__", expected)
    (tool_dir / "IcarusAuthority.kt").write_text(authority, encoding="utf-8")

    executor = tool_dir / "ToolCallExecutor.kt"
    once(executor,
         '        val tool = registry.byName(call.name)',
         '        // ICARUS must authorize before any Hermes tool implementation is entered.\n'
         '        IcarusAuthority.deniedReason(call.name, call.arguments)?.let { return ToolResult.error(it) }\n'
         '        val tool = registry.byName(call.name)')

    # Unlike the donor callback, this entry never auto-approves read-only,
    # phone, or Home Assistant actions. Each interactive tool call must
    # actually be approved in the owner's native dialog.
    confirmation = engine / "core/domain/src/main/kotlin/com/hermes/agent/domain/tool/ToolConfirmationService.kt"
    once(confirmation,
         '    suspend fun awaitConfirmation(call: ToolCall): Boolean = requestMutex.withLock {',
         '''    suspend fun awaitExplicitOwnerConfirmation(call: ToolCall): Boolean = requestMutex.withLock {
        val deferred = CompletableDeferred<Boolean>()
        pendingDeferred = deferred
        val request = PendingConfirmation(UUID.randomUUID().toString(), call)
        _pendingRequest.value = request
        Timber.tag("IcarusOwnerPermit").i("Waiting for owner request=%s tool=%s", request.id, call.name)
        try {
            kotlinx.coroutines.withTimeoutOrNull(CONFIRMATION_TIMEOUT_MS) { deferred.await() } ?: false
        } finally {
            _pendingRequest.value = null
            pendingDeferred = null
        }
    }

    suspend fun awaitConfirmation(call: ToolCall): Boolean = requestMutex.withLock {''')

    # The deferred-tool bridge calls raw Tool.execute directly. Close the
    # bypass at its actual target dispatch, not only the outer tool executor.
    bridge = engine / "core/tools/src/main/kotlin/com/hermes/agent/data/tools/ToolCallTool.kt"
    once(bridge,
         'import com.hermes.agent.domain.tool.Tool\n',
         'import com.hermes.agent.domain.tool.Tool\n'
         'import com.hermes.agent.data.tool.IcarusAuthority\n')
    once(bridge,
         '        return targetTool.execute(toolArgs)',
         '        IcarusAuthority.deniedReason(toolName, toolArgs)?.let { return ToolResult.error(it) }\n'
         '        return targetTool.execute(toolArgs)')

    # Do not let the donor's own bootstrap reschedule cron, plugins or proactive
    # actions before ICARUS has a separately reviewed owner-approved route.
    # Keep only platform-required WorkManager initialization, logging, memory
    # pressure handling and settings warm-up for interactive chat/inference.
    startup_worker = app / "src/main/kotlin/com/hermes/agent/HermesAppStartup.kt"
    once(startup_worker,
         '        // Secrets restored from another install are sealed with that install\'s',
         '        // ICARUS owns autonomous work: no Hermes startup jobs without owner permits.\n'
         '        if (!com.hermes.agent.data.tool.IcarusAuthority.donorAutonomyPermitted()) {\n'
         '            memoryPressureMonitor.start()\n'
         '            warmUpSettingsStore()\n'
         '            return\n'
         '        }\n'
         '        // Secrets restored from another install are sealed with that install\'s')

    module = app / "src/main/kotlin/com/hermes/agent/data/agent"
    orchestrator = module / "OrchestratorImpl.kt"
    once(orchestrator,
         'IcarusIdentity.ROOT + "\\n\\n" + IcarusLineage.promptPrefix() + "\\n\\n" + persona',
         'IcarusIdentity.ROOT + "\\n\\n" + ' +
         'com.hermes.agent.data.tool.IcarusAuthority.promptContext() + "\\n\\n" + ' +
         '"Hermes is an execution worker; ICARUS owns the policy and memory.\\n\\n" + persona')
    # Deterministic runtime probe: invoke the actual registered memory tool
    # through the shared executor and compare durable Room contents before/after.
    # The model cannot answer or forge this test.
    once(orchestrator,
         'import com.hermes.agent.domain.llm.LlmMessage\n',
         'import com.hermes.agent.domain.llm.LlmMessage\n'
         'import com.hermes.agent.domain.llm.ToolCall\n'
         'import kotlinx.serialization.json.JsonPrimitive\n'
         'import kotlinx.coroutines.flow.first\n')
    hook = '    ): Flow<OrchestratorEvent> = channelFlow {\n'
    insertion = (
        '        if (userMessage.trim().equals("/icarus authority test", ignoreCase = true)) {\n'
        '            val marker = "ICARUS-AUTHORITY-TEST-002"\n'
        '            val registered = toolRegistry.byName("memory") != null\n'
        '            val before = memoryRepository.observeMemories().first().any { it.content == marker }\n'
        '            val attempted = ToolCall(\n'
        '                id = "icarus-authority-test",\n'
        '                name = "memory",\n'
        '                arguments = mapOf(\n'
        '                    "action" to JsonPrimitive("add"),\n'
        '                    "content" to JsonPrimitive(marker),\n'
        '                ),\n'
        '            )\n'
        '            val outcome = if (registered) {\n'
        '                toolCallExecutor.execute(attempted, confirmationGate = null)\n'
        '            } else {\n'
        '                ToolResult.error("ICARUS_NO_REGISTERED_MEMORY_TOOL")\n'
        '            }\n'
        '            val after = memoryRepository.observeMemories().first().any { it.content == marker }\n'
        '            activityLedger.record(ActivityEntry(\n'
        '                timestamp = System.currentTimeMillis(),\n'
        '                kind = ActivityKind.TOOL_CALL,\n'
        '                origin = "icarus_supervisor_probe",\n'
        '                conversationId = conversationId,\n'
        '                title = "memory:add",\n'
        '                detail = (outcome.errorMessage ?: outcome.output).take(500),\n'
        '                success = outcome.success,\n'
        '            ))\n'
        '            val report = "ICARUS_AUTHORITY_PROBE\\n" +\n'
        '                "REGISTERED_MEMORY_TOOL=" + registered + "\\n" +\n'
        '                "EXECUTOR_CALLED=" + registered + "\\n" +\n'
        '                "EXECUTION_SUCCESS=" + outcome.success + "\\n" +\n'
        '                "RAW_DENIAL=" + (outcome.errorMessage ?: "(none)") + "\\n" +\n'
        '                "MARKER_PRESENT_BEFORE=" + before + "\\n" +\n'
        '                "MARKER_PRESENT_AFTER=" + after + "\\n" +\n'
        '                "MODEL_INFERENCE_USED=false\\n" +\n'
        '                "LOG=ActivityLedger/memory:add"\n'
        '            send(OrchestratorEvent.ReplyToken(report))\n'
        '            send(OrchestratorEvent.ReplyComplete(report, AgentRole.CONVERSATIONAL, isOnDevice = true))\n'
        '            return@channelFlow\n'
        '        }\n'
    )
    once(orchestrator, hook, hook + insertion)

    # Remove previously staged prompt-adjacent default deny; central executor owns it.
    once(orchestrator,
         '                    !IcarusExecutionGate.isAuthorized(deterministic.call.name) ->\n'
         '                        ToolResult.error("ICARUS_PERMIT_REQUIRED: action denied")\n', '')
    once(orchestrator,
         '    ): Flow<OrchestratorEvent> = channelFlow {\n',
         '    ): Flow<OrchestratorEvent> = channelFlow {\n'
         '        // Independent of chat ID and selected LLM, ICARUS must be ready.\n'
         '        com.hermes.agent.data.tool.IcarusAuthority.requireReady()\n'
         '        // ICARUS speaks for its own memory without relying on a model guess.\n'
         '        if (com.hermes.agent.data.tool.IcarusAuthority.isMemoryInspectionRequest(userMessage)) {\n'
         '            val report = com.hermes.agent.data.tool.IcarusAuthority.memoryReport()\n'
         '            send(OrchestratorEvent.ReplyToken(report))\n'
         '            send(OrchestratorEvent.ReplyComplete(report, AgentRole.CONVERSATIONAL, isOnDevice = true))\n'
         '            return@channelFlow\n'
         '        }\n')

    # Every interactive command is approved by Michael, not by Hermes's
    # default-allow policy or a model's text response.
    once(orchestrator,
         '                val mustConfirm = decision is ToolExecutionDecision.Confirm\n',
         '                val mustConfirm = true // ICARUS requires owner approval for every action\n')
    once(orchestrator,
         '                    mustConfirm && !toolConfirmationService.awaitConfirmation(deterministic.call) ->\n'
         '                        ToolResult.error("Action cancelled")\n'
         '                    else -> toolCallExecutor.execute(deterministic.call, confirmationGate = null)',
         '                    origin != ExecutionOrigin.INTERACTIVE ->\n'
         '                        ToolResult.error("ICARUS_PERMIT_REQUIRED: interactive owner approval required")\n'
         '                    !toolConfirmationService.awaitExplicitOwnerConfirmation(deterministic.call) ->\n'
         '                        ToolResult.error("ICARUS_OWNER_DECLINED: action not approved")\n'
         '                    else -> {\n'
         '                        com.hermes.agent.data.tool.IcarusAuthority.approveOwnerConfirmed(\n'
         '                            deterministic.call.name, deterministic.call.arguments)\n'
         '                        toolCallExecutor.execute(deterministic.call, confirmationGate = null)\n'
         '                    }')
    # ICARUS is the global chat controller. Hermes's role/persona-specific
    # tool catalogue must not hide available capabilities from ICARUS.
    # Every execution remains subject to native owner confirmation.
    once(orchestrator,
         '            val availableTools = when {\\n'
         '                // A persona chat is just a chat: offering the full catalogue to a small\\n'
         '                // on-device model made it improvise calls to unrelated tools (desktop_bots,\\n'
         '                // kanban) instead of answering. The Chief of Bots gets exactly one tool.\\n'
         '                localBotStore.isChiefOfBots(conversationId) ->\\n'
         '                    listOfNotNull(toolRegistry.byName("manage_bots")?.descriptor)\\n'
         '                localBotStore.isLocalBot(conversationId) -> emptyList()\\n'
         '                else -> agent.availableTools(toolRegistry)\\n'
         '            }',
         '            val availableTools = toolRegistry.descriptors() // ICARUS: all chats, all registered capabilities')

    # The LLM callback is also required to use explicit native confirmation.
    once(orchestrator,
         'if (requiresConfirmation) toolConfirmationService.awaitConfirmation(call) else true',
         'if (requiresConfirmation) toolConfirmationService.awaitExplicitOwnerConfirmation(call) else false')

    # Hermes silently writes memory through ConversationLearner after a reply.
    # Do not let this background path bypass ICARUS's no-write policy.
    once(orchestrator,
         '        learningScope.launch {\n'
         '            // Extract personal facts from this turn.',
         '        if (com.hermes.agent.data.tool.IcarusAuthority.donorAutonomyPermitted()) {\n'
         '        learningScope.launch {\n'
         '            // Extract personal facts from this turn.')
    once(orchestrator,
         '            userModelService.onConversationComplete()\n'
         '        }\n',
         '            userModelService.onConversationComplete()\n'
         '        }\n'
         '        }\n')

    loop = module / "AgentLoopRunner.kt"
    once(loop,
         'import com.hermes.agent.data.tool.ToolCallExecutor\n',
         'import com.hermes.agent.data.tool.ToolCallExecutor\n'
         'import com.hermes.agent.data.tool.IcarusAuthority\n')
    once(loop,
         '                val mustConfirm = decision is ToolExecutionDecision.Confirm\n',
         '                val mustConfirm = true // native owner approval required for every tool action\n')
    once(loop,
         '                        decision !is ToolExecutionDecision.Deny\n',
         '                        decision !is ToolExecutionDecision.Deny && origin == ExecutionOrigin.INTERACTIVE\n')
    once(loop,
         '                    // Headless: there was no gate to ask, so a confirmation-required\n'
         '                    // tool still cannot run. Unchanged from before this fix.\n'
         '                    mustConfirm && confirmed != true -> ToolResult.error("user declined")',
         '                    // ICARUS does not let background workers mint owner permits.\n'
         '                    origin != ExecutionOrigin.INTERACTIVE ->\n'
         '                        ToolResult.error("ICARUS_PERMIT_REQUIRED: interactive owner approval required")\n'
         '                    mustConfirm && confirmed != true -> ToolResult.error("ICARUS_OWNER_DECLINED")')
    once(loop,
         '                    else -> toolCallExecutor.execute(call, confirmationGate = null).also {\n',
         '                    else -> {\n'
         '                        IcarusAuthority.approveOwnerConfirmed(call.name, call.arguments)\n'
         '                        if (call.name == ToolSearchEngine.TOOL_CALL_NAME && gateName != call.name) {\n'
         '                            IcarusAuthority.approveOwnerConfirmed(gateName, gateArgs)\n'
         '                        }\n'
         '                        toolCallExecutor.execute(call, confirmationGate = null).also {\n')
    once(loop,
         '                        if (call.id.startsWith(RECOVERED_CALL_PREFIX)) recoveredResults[signature] = it\n'
         '                    }\n',
         '                        if (call.id.startsWith(RECOVERED_CALL_PREFIX)) recoveredResults[signature] = it\n'
         '                        }\n'
         '                    }\n')
    once(loop,
         ' !IcarusExecutionGate.isAuthorized(gateName) -> '
         'ToolResult.error("ICARUS_PERMIT_REQUIRED: action denied")\n'
         '                    ', '')

    # Local source assertions: evidence of placement, NOT device/runtime proof.
    assert "IcarusApplicationLike" in out_loader.read_text()
    assert "IcarusAuthority.bootstrap(app)" in out_delegate.read_text()
    assert "IcarusAuthority.deniedReason(call.name, call.arguments)" in executor.read_text()
    assert "IcarusAuthority.memoryReport()" in orchestrator.read_text()
    assert "IcarusAuthority.donorAutonomyPermitted()" in startup_worker.read_text()
    print("ICARUS_SUPERVISOR_SOURCE_INSTALLED; memory SHA pinned; central tools fail closed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-checkout", required=True)
    parser.add_argument("--lineage-root", required=True)
    args = parser.parse_args()
    install(Path(args.hermes_checkout), Path(args.lineage_root))
