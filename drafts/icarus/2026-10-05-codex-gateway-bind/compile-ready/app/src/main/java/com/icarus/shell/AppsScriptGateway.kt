package com.icarus.shell

import android.app.Application
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URI
import java.security.KeyStore
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class SecureStore(app: Application) {
    private val prefs = app.getSharedPreferences("icarus_gateway", 0)
    private val alias = "icarus_device_token"
    var backendUrl: String
        get() = prefs.getString("backend_url", "") ?: ""
        set(value) { prefs.edit().putString("backend_url", value).remove("device_token").apply() }
    val deviceId: String
        get() = prefs.getString("device_id", null) ?: UUID.randomUUID().toString().also {
            prefs.edit().putString("device_id", it).apply()
        }
    private fun key(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getKey(alias, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
    var token: String
        get() {
            val saved = prefs.getString("device_token", null) ?: return ""
            return try {
                val chunks = saved.split(":")
                val cipher = Cipher.getInstance("AES/GCM/NoPadding")
                cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, Base64.decode(chunks[0], Base64.NO_WRAP)))
                String(cipher.doFinal(Base64.decode(chunks[1], Base64.NO_WRAP)), Charsets.UTF_8)
            } catch (_: Exception) { prefs.edit().remove("device_token").apply(); "" }
        }
        set(value) {
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.ENCRYPT_MODE, key())
            val saved = Base64.encodeToString(cipher.iv, Base64.NO_WRAP) + ":" +
                Base64.encodeToString(cipher.doFinal(value.toByteArray(Charsets.UTF_8)), Base64.NO_WRAP)
            prefs.edit().putString("device_token", saved).commit()
        }
}

class IcarusApiClient(private val endpointProvider: () -> String) {
    suspend fun post(body: JSONObject): JSONObject = withContext(Dispatchers.IO) {
        val uri = URI(endpointProvider())
        require(uri.scheme == "https" && !uri.host.isNullOrBlank() && uri.userInfo == null) { "Valid HTTPS endpoint required." }
        val connection = uri.toURL().openConnection() as HttpURLConnection
        try {
            connection.requestMethod = "POST"
            connection.connectTimeout = 15000
            connection.readTimeout = 20000
            connection.instanceFollowRedirects = true
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            connection.setRequestProperty("Accept", "application/json")
            connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            val code = connection.responseCode
            require(code in 200..299) { "Gateway HTTP $code; request outcome may be unknown." }
            val raw = connection.inputStream.bufferedReader().use { it.readText() }
            require(raw.length <= 1_048_576) { "Gateway response too large." }
            val envelope = JSONObject(raw)
            require(envelope.optBoolean("ok", false)) { "Gateway rejected request; inspect server logs." }
            envelope.getJSONObject("data")
        } finally { connection.disconnect() }
    }
}

class AppsScriptExecutionGateway(private val app: Application) : ExecutionGateway {
    private val store = SecureStore(app)
    private val client = IcarusApiClient { store.backendUrl }
    @Volatile private var stopped = false
    fun backendUrl() = store.backendUrl
    fun setBackendUrl(value: String) { if (value.trim() != store.backendUrl) store.backendUrl = value.trim() }
    fun isPaired() = store.token.isNotBlank()
    suspend fun pair(code: String) {
        val data = client.post(JSONObject().put("op", "pair").put("deviceId", store.deviceId)
            .put("pairingCode", code).put("clientVersion", "0.1-shell-gateway"))
        require(data.getString("deviceId") == store.deviceId) { "Pair response device mismatch." }
        val token = data.getString("token")
        require(token.isNotBlank()) { "Pair returned no token." }
        store.token = token
    }
    private fun authenticated(op: String) = JSONObject().put("op", op).put("deviceId", store.deviceId).put("token", store.token)
    override suspend fun submit(request: TaskRequest): TaskResult {
        require(isPaired()) { "Pair this device first." }
        stopped = false
        val deadline = android.os.SystemClock.elapsedRealtime() + 60000
        var data = client.post(authenticated("submit").put("clientTaskId", UUID.randomUUID().toString()).put("text", request.problem))
        val taskId = data.getString("task_id")
        while (!stopped && android.os.SystemClock.elapsedRealtime() < deadline && active(data)) {
            delay(2000)
            if (!stopped && android.os.SystemClock.elapsedRealtime() < deadline) {
                val next = client.post(authenticated("status").put("taskId", taskId))
                require(next.getString("task_id") == taskId) { "Status response task mismatch." }
                data = next
            }
        }
        val result = snapshot(data)
        return if (stopped) result.copy(summary = "Stopped waiting locally; remote task may continue.") else result
    }
    private fun active(data: JSONObject): Boolean {
        val status = data.optString("status").uppercase()
        val evidence = data.optString("evidence_ref")
        return status in setOf("REQUESTED", "QUEUED", "CLAIMED", "INSPECTING", "EXECUTING", "SUBMITTING", "RUNNING") &&
            !evidence.contains("WORK COMPLETE", true) && !evidence.contains("result=", true)
    }
    private fun snapshot(data: JSONObject): TaskResult {
        val status = data.getString("status").uppercase()
        val evidence = data.optString("evidence_ref")
        val stage = when {
            status == "PASS" -> TaskStage.PASS
            status == "BLOCKED" -> TaskStage.BLOCKED
            status in setOf("FAIL", "FAILED") -> TaskStage.FAILED
            status.contains("VERIFY") || status.startsWith("WORK_COMPLETE") || evidence.contains("WORK COMPLETE", true) || evidence.contains("result=", true) -> TaskStage.VERIFYING
            else -> TaskStage.EXECUTING
        }
        val summary = if (evidence.contains("result=", true)) evidence.substring(evidence.indexOf("result=", ignoreCase = true) + 7).take(2000)
            else "Backend status: $status. " + data.optString("objective").take(500)
        val proof = listOf(ProofItem("Task ID", data.getString("task_id")), ProofItem("Backend status", status)) +
            if (evidence.isNotBlank()) listOf(ProofItem("Evidence", evidence.take(4000))) else emptyList()
        return TaskResult(stage, summary, proof)
    }
    override suspend fun cancel() { stopped = true }
}
