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
import java.security.MessageDigest
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.Mac
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

class SecureStore(app: Application) {
    private val prefs = app.getSharedPreferences("icarus_gateway", 0)
    private val alias = "icarus_device_token"

    var backendUrl: String
        get() = prefs.getString("backend_url", "") ?: ""
        set(value) {
            val clean = value.trim()
            if (clean != backendUrl) {
                prefs.edit().putString("backend_url", clean).remove("device_token").apply()
            }
        }

    val deviceId: String
        get() = prefs.getString("device_id", null) ?: UUID.randomUUID().toString().also {
            prefs.edit().putString("device_id", it).apply()
        }

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

    var token: String
        get() {
            val saved = prefs.getString("device_token", null) ?: return ""
            return try {
                val chunks = saved.split(":")
                require(chunks.size == 2)
                val cipher = Cipher.getInstance("AES/GCM/NoPadding")
                cipher.init(
                    Cipher.DECRYPT_MODE,
                    key(),
                    GCMParameterSpec(128, Base64.decode(chunks[0], Base64.NO_WRAP))
                )
                String(
                    cipher.doFinal(Base64.decode(chunks[1], Base64.NO_WRAP)),
                    Charsets.UTF_8
                )
            } catch (_: Exception) {
                prefs.edit().remove("device_token").apply()
                ""
            }
        }
        set(value) {
            require(value.isNotBlank())
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.ENCRYPT_MODE, key())
            val saved =
                Base64.encodeToString(cipher.iv, Base64.NO_WRAP) + ":" +
                    Base64.encodeToString(
                        cipher.doFinal(value.toByteArray(Charsets.UTF_8)),
                        Base64.NO_WRAP
                    )
            prefs.edit().putString("device_token", saved).commit()
        }
}

class IcarusApiClient(private val endpointProvider: () -> String) {
    suspend fun post(body: JSONObject): JSONObject = withContext(Dispatchers.IO) {
        val uri = URI(endpointProvider())
        require(
            uri.scheme == "https" && !uri.host.isNullOrBlank() && uri.userInfo == null
        ) { "Valid HTTPS endpoint required." }

        val connection = uri.toURL().openConnection() as HttpURLConnection
        try {
            connection.requestMethod = "POST"
            connection.connectTimeout = 15000
            connection.readTimeout = 25000
            connection.instanceFollowRedirects = true
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            connection.setRequestProperty("Accept", "application/json")
            connection.outputStream.use {
                it.write(body.toString().toByteArray(Charsets.UTF_8))
            }

            val code = connection.responseCode
            val stream =
                if (code in 200..299) connection.inputStream else connection.errorStream
            val raw = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
            require(raw.length <= 1_048_576) { "Gateway response too large." }
            require(code in 200..299) { "Gateway HTTP $code." }

            val envelope = JSONObject(raw)
            require(envelope.optBoolean("ok", false)) {
                envelope.optString("error", "Gateway rejected request.").take(240)
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

    @Volatile
    private var stopped = false

    fun backendUrl() = store.backendUrl

    fun setBackendUrl(value: String) {
        store.backendUrl = value
    }

    fun isPaired() = store.token.isNotBlank()

    suspend fun pair(code: String) {
        val data = client.post(
            JSONObject()
                .put("op", "pair")
                .put("deviceId", store.deviceId)
                .put("pairingCode", code)
                .put("clientVersion", "0.4.1-clean-recovery")
        )
        require(data.getString("deviceId") == store.deviceId) {
            "Pair response device mismatch."
        }
        val token = data.getString("token")
        require(token.isNotBlank()) { "Pair returned no token." }
        store.token = token
    }

    private fun sha256Hex(value: String): String {
        return MessageDigest.getInstance("SHA-256")
            .digest(value.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it) }
    }

    private fun hmacSha256Hex(keyText: String, message: String): String {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(
            SecretKeySpec(
                keyText.toByteArray(Charsets.UTF_8),
                "HmacSHA256"
            )
        )
        return mac.doFinal(message.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it) }
    }

    private fun signedEnvelope(inner: JSONObject): JSONObject {
        val token = store.token
        require(token.isNotBlank()) { "Pair this device first." }

        val payload = inner.toString()
        require(payload.length <= 30000) { "Signed payload too large." }

        val timestamp = System.currentTimeMillis()
        val nonce = UUID.randomUUID().toString()
        val tokenHashHex = sha256Hex(token)
        val signingText =
            "ICARUS_QUEUE_V1\n" +
                store.deviceId + "\n" +
                timestamp + "\n" +
                nonce + "\n" +
                payload
        val signature = hmacSha256Hex(tokenHashHex, signingText)

        return JSONObject()
            .put("v", 1)
            .put("deviceId", store.deviceId)
            .put("timestamp", timestamp)
            .put("nonce", nonce)
            .put("payload", payload)
            .put("signature", signature)
    }

    private suspend fun signed(inner: JSONObject): JSONObject {
        require(inner.optString("deviceId") == store.deviceId) {
            "Inner device identity mismatch."
        }
        require(!inner.has("token")) { "Token must not appear inside signed payload." }
        return client.post(signedEnvelope(inner))
    }

    private fun inner(op: String): JSONObject =
        JSONObject()
            .put("op", op)
            .put("deviceId", store.deviceId)

    override suspend fun submit(request: TaskRequest): TaskResult {
        require(isPaired()) { "Pair this device first." }
        stopped = false

        val deadline = android.os.SystemClock.elapsedRealtime() + 60000L
        var data = signed(
            inner("submit")
                .put("clientTaskId", UUID.randomUUID().toString())
                .put("text", request.problem)
        )
        val taskId = data.getString("task_id")

        while (
            !stopped &&
            android.os.SystemClock.elapsedRealtime() < deadline &&
            isActivelyProgressing(data)
        ) {
            delay(2000)
            if (!stopped && android.os.SystemClock.elapsedRealtime() < deadline) {
                val next = signed(
                    inner("status").put("taskId", taskId)
                )
                require(next.getString("task_id") == taskId) {
                    "Status response task mismatch."
                }
                data = next
            }
        }

        if (stopped) {
            return TaskResult(
                stage = TaskStage.IDLE,
                summary = "Stopped waiting locally; remote task may continue.",
                proof = listOf(ProofItem("Task ID", taskId))
            )
        }

        if (
            android.os.SystemClock.elapsedRealtime() >= deadline &&
            isActivelyProgressing(data)
        ) {
            return TaskResult(
                stage = TaskStage.VERIFYING,
                summary = "Local wait ended after 60 seconds. The remote task may still be running; this screen is released.",
                proof = listOf(
                    ProofItem("Task ID", taskId),
                    ProofItem("Backend status", data.optString("status").uppercase())
                )
            )
        }

        return snapshot(data)
    }

    private fun isActivelyProgressing(data: JSONObject): Boolean {
        val status = data.optString("status").uppercase()
        val evidence = data.optString("evidence_ref")

        if (
            evidence.contains("WORK COMPLETE", true) ||
            evidence.contains("result=", true)
        ) {
            return false
        }

        return status in setOf(
            "REQUESTED",
            "QUEUED",
            "CLAIMED",
            "INSPECTING",
            "REASONING",
            "READY_FOR_EXECUTION",
            "EXECUTING",
            "SUBMITTING",
            "RUNNING"
        )
    }

    private fun snapshot(data: JSONObject): TaskResult {
        val status = data.optString("status").uppercase().ifBlank { "UNKNOWN" }
        val evidence = data.optString("evidence_ref")
        val stage = when {
            status == "PASS" -> TaskStage.PASS
            status == "BLOCKED" -> TaskStage.BLOCKED
            status == "WAITING_REASONING_CAPACITY" -> TaskStage.BLOCKED
            status == "PENDING_AUTH" -> TaskStage.BLOCKED
            status in setOf("FAIL", "FAILED") -> TaskStage.FAILED
            status.contains("VERIFY") -> TaskStage.VERIFYING
            status.startsWith("WORK_COMPLETE") -> TaskStage.VERIFYING
            evidence.contains("WORK COMPLETE", true) -> TaskStage.VERIFYING
            evidence.contains("result=", true) -> TaskStage.VERIFYING
            isActivelyProgressing(data) -> TaskStage.VERIFYING
            else -> TaskStage.FAILED
        }

        val resultObject = data.opt("result")
        val resultText =
            when (resultObject) {
                null, JSONObject.NULL -> ""
                is String -> resultObject
                else -> resultObject.toString()
            }.take(4000)

        val summary = when {
            resultText.isNotBlank() -> resultText
            evidence.contains("result=", true) ->
                evidence.substring(
                    evidence.indexOf("result=", ignoreCase = true) + 7
                ).take(2000)
            status == "WAITING_REASONING_CAPACITY" ->
                "Reasoning capacity is temporarily unavailable. The local composer is released."
            status == "PENDING_AUTH" ->
                "Backend authorization is required. The local composer is released."
            else ->
                "Backend status: $status. " + data.optString("objective").take(500)
        }

        val proof = mutableListOf(
            ProofItem("Task ID", data.optString("task_id")),
            ProofItem("Backend status", status)
        )
        if (evidence.isNotBlank()) {
            proof += ProofItem("Evidence", evidence.take(4000))
        }
        if (data.optString("auth_url").isNotBlank()) {
            proof += ProofItem("Authorization URL", data.optString("auth_url").take(2000))
        }
        if (data.optString("evidence_fingerprint").isNotBlank()) {
            proof += ProofItem(
                "Evidence fingerprint",
                data.optString("evidence_fingerprint").take(256)
            )
        }

        return TaskResult(stage, summary, proof)
    }

    override suspend fun cancel() {
        stopped = true
    }
}
