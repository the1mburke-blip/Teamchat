package com.aistudio.icarus.appsscript

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
import java.security.MessageDigest
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.Mac
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

private fun hex(bytes: ByteArray): String = bytes.joinToString("") { "%02x".format(it.toInt() and 0xff) }
private fun sha256Hex(value: String): String = hex(MessageDigest.getInstance("SHA-256").digest(value.toByteArray(Charsets.UTF_8)))
private fun hmacSha256Hex(keyText: String, message: String): String {
    val mac = Mac.getInstance("HmacSHA256")
    mac.init(SecretKeySpec(keyText.toByteArray(Charsets.UTF_8), "HmacSHA256"))
    return hex(mac.doFinal(message.toByteArray(Charsets.UTF_8)))
}

class SecureStore(app: Application) {
    private val prefs = app.getSharedPreferences("icarus_signed_v1", 0)
    private val alias = "icarus_recovery_token"

    val backendUrl: String get() = prefs.getString("backend_url", "") ?: ""
    val deviceId: String get() = prefs.getString("device_id", "") ?: ""

    private fun key(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getKey(alias, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(
                KeyGenParameterSpec.Builder(
                    alias,
                    KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
                )
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .build()
            )
        }.generateKey()
    }

    val token: String
        get() {
            val saved = prefs.getString("device_token", null) ?: return ""
            return try {
                val chunks = saved.split(":", limit = 2)
                require(chunks.size == 2)
                val cipher = Cipher.getInstance("AES/GCM/NoPadding")
                cipher.init(
                    Cipher.DECRYPT_MODE,
                    key(),
                    GCMParameterSpec(128, Base64.decode(chunks[0], Base64.NO_WRAP))
                )
                String(cipher.doFinal(Base64.decode(chunks[1], Base64.NO_WRAP)), Charsets.UTF_8)
            } catch (_: Exception) {
                ""
            }
        }

    fun saveRecovery(endpoint: String, deviceId: String, token: String) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val encrypted = Base64.encodeToString(cipher.iv, Base64.NO_WRAP) + ":" +
            Base64.encodeToString(cipher.doFinal(token.toByteArray(Charsets.UTF_8)), Base64.NO_WRAP)
        prefs.edit()
            .putString("backend_url", endpoint)
            .putString("device_id", deviceId)
            .putString("device_token", encrypted)
            .commit()
    }

    fun clearRecovery() {
        prefs.edit().remove("backend_url").remove("device_id").remove("device_token").commit()
    }
}

class IcarusApiClient(private val endpointProvider: () -> String) {
    suspend fun post(body: JSONObject): JSONObject = withContext(Dispatchers.IO) {
        val uri = URI(endpointProvider())
        require(uri.scheme == "https" && !uri.host.isNullOrBlank() && uri.userInfo == null) {
            "Valid HTTPS endpoint required."
        }
        val connection = uri.toURL().openConnection() as HttpURLConnection
        try {
            connection.requestMethod = "POST"
            connection.connectTimeout = 15000
            connection.readTimeout = 30000
            connection.instanceFollowRedirects = true
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            connection.setRequestProperty("Accept", "application/json")
            connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val raw = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
            require(raw.length <= 1_048_576) { "Gateway response too large." }
            require(raw.isNotBlank()) { "Gateway returned an empty response." }
            val envelope = JSONObject(raw)
            if (!envelope.optBoolean("ok", false)) {
                throw IllegalStateException(envelope.optString("error", "Gateway rejected request."))
            }
            envelope.getJSONObject("data")
        } finally {
            connection.disconnect()
        }
    }
}

class AppsScriptExecutionGateway(private val app: Application) : ExecutionGateway {
    private val store = SecureStore(app)
    private val client = IcarusApiClient { store.backendUrl }
    @Volatile private var stopped = false

    fun backendUrl(): String = store.backendUrl
    fun deviceId(): String = store.deviceId
    fun isProvisioned(): Boolean = store.backendUrl.isNotBlank() && store.deviceId.isNotBlank() && store.token.isNotBlank()

    suspend fun recover(endpoint: String, deviceId: String, token: String): String {
        val cleanEndpoint = endpoint.trim()
        val cleanDeviceId = deviceId.trim()
        val cleanToken = token.trim()
        val uri = URI(cleanEndpoint)
        require(uri.scheme == "https" && !uri.host.isNullOrBlank() && uri.userInfo == null) { "Valid HTTPS endpoint required." }
        require(cleanDeviceId.matches(Regex("[A-Za-z0-9_-]{16,128}"))) { "Valid recovery device ID required." }
        require(cleanToken.length in 24..2048) { "Valid recovery token required." }
        store.saveRecovery(cleanEndpoint, cleanDeviceId, cleanToken)
        return try {
            val runtime = postSigned(JSONObject().put("op", "runtime").put("deviceId", cleanDeviceId))
            runtime.optString("runtimeVersion", "CONNECTED")
        } catch (t: Throwable) {
            store.clearRecovery()
            throw t
        }
    }

    private suspend fun postSigned(inner: JSONObject): JSONObject {
        require(isProvisioned()) { "Recover this device first." }
        inner.put("deviceId", store.deviceId)
        val payload = inner.toString()
        require(payload.length <= 30000) { "Signed payload too large." }
        val timestamp = System.currentTimeMillis()
        val nonce = UUID.randomUUID().toString()
        val tokenHashHex = sha256Hex(store.token)
        val signingText = "ICARUS_QUEUE_V1\n${store.deviceId}\n$timestamp\n$nonce\n$payload"
        val signature = hmacSha256Hex(tokenHashHex, signingText)
        val envelope = JSONObject()
            .put("v", 1)
            .put("deviceId", store.deviceId)
            .put("timestamp", timestamp)
            .put("nonce", nonce)
            .put("payload", payload)
            .put("signature", signature)
        return client.post(envelope)
    }

    override suspend fun submit(request: TaskRequest): TaskResult {
        require(isProvisioned()) { "Recover this device first." }
        stopped = false
        val deadline = android.os.SystemClock.elapsedRealtime() + 60000
        var data = postSigned(
            JSONObject()
                .put("op", "submit")
                .put("deviceId", store.deviceId)
                .put("clientTaskId", UUID.randomUUID().toString())
                .put("text", request.problem)
        )
        val taskId = data.getString("task_id")
        while (!stopped && android.os.SystemClock.elapsedRealtime() < deadline && isActive(data)) {
            delay(2000)
            if (!stopped && android.os.SystemClock.elapsedRealtime() < deadline) {
                val next = postSigned(
                    JSONObject()
                        .put("op", "status")
                        .put("deviceId", store.deviceId)
                        .put("taskId", taskId)
                )
                require(next.getString("task_id") == taskId) { "Status response task mismatch." }
                data = next
            }
        }
        if (stopped || isActive(data)) {
            return TaskResult(
                stage = TaskStage.OUTCOME_UNKNOWN,
                summary = if (stopped) "Stopped waiting locally; the remote task may still continue." else "Polling ended before a terminal server state; check the same task before resubmitting.",
                proof = listOf(
                    ProofItem("Task ID", taskId),
                    ProofItem("Backend status", data.optString("status", "UNKNOWN"))
                )
            )
        }
        return snapshot(data)
    }

    private fun isActive(data: JSONObject): Boolean {
        return data.optString("status").uppercase() in setOf(
            "REQUESTED", "QUEUED", "CLAIMED", "INSPECTING", "REASONING",
            "EXECUTING", "SUBMITTING", "RUNNING"
        )
    }

    private fun snapshot(data: JSONObject): TaskResult {
        val status = data.optString("status", "UNKNOWN").uppercase()
        val evidence = data.optString("evidence_ref")
        val resultText = data.opt("result")?.toString().orEmpty()
        val stage = when {
            status == "PASS" -> TaskStage.PASS
            status == "BLOCKED" || status == "WAITING_REASONING_CAPACITY" || status == "PENDING_AUTH" -> TaskStage.BLOCKED
            status in setOf("FAIL", "FAILED") -> TaskStage.FAILED
            status.contains("VERIFY") || status.startsWith("WORK_COMPLETE") -> TaskStage.VERIFYING
            else -> TaskStage.OUTCOME_UNKNOWN
        }
        val summary = when {
            resultText.isNotBlank() -> resultText.take(4000)
            evidence.isNotBlank() -> evidence.take(2000)
            else -> "Backend status: $status. " + data.optString("objective").take(500)
        }
        val proof = mutableListOf(
            ProofItem("Task ID", data.optString("task_id", "unknown")),
            ProofItem("Backend status", status)
        )
        data.optString("evidence_fingerprint").takeIf { it.isNotBlank() }?.let { proof += ProofItem("Evidence fingerprint", it) }
        data.optString("composio_tool").takeIf { it.isNotBlank() }?.let { proof += ProofItem("Tool", it) }
        data.optString("auth_url").takeIf { it.isNotBlank() }?.let { proof += ProofItem("Authorization", it.take(1000)) }
        if (evidence.isNotBlank()) proof += ProofItem("Evidence", evidence.take(4000))
        return TaskResult(stage, summary, proof)
    }

    override suspend fun cancel() {
        stopped = true
    }
}
