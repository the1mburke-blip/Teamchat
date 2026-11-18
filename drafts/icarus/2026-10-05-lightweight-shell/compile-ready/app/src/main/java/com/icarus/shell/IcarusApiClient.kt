package com.aistudio.icarus.appsscript

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.UUID
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

class IcarusApiClient(
    private val endpointProvider: () -> String,
    private val deviceIdProvider: () -> String
) {
    data class RuntimeInfo(val runtimeVersion: String, val environment: String)

    data class TaskSnapshot(
        val taskId: String,
        val status: String,
        val objective: String,
        val evidence: String,
        val resultText: String
    )

    suspend fun runtime(token: String): RuntimeInfo = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("op", "runtime")
            .put("deviceId", deviceIdProvider())
        val root = signedPost(token, body)
        val data = requireOk(root)
        RuntimeInfo(
            runtimeVersion = data.optString("runtimeVersion"),
            environment = data.optString("environment", "NON_PROD")
        )
    }

    suspend fun submit(token: String, text: String): TaskSnapshot = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("op", "submit")
            .put("deviceId", deviceIdProvider())
            .put("clientTaskId", UUID.randomUUID().toString())
            .put("text", boundedObjective(text))

        var task = taskFrom(requireOk(signedPost(token, body)))
        var polls = 0

        while (isActive(task.status) && task.taskId.isNotBlank() && polls < 18) {
            delay(2_000)
            task = statusInternal(token, task.taskId)
            polls++
        }

        task
    }

    suspend fun status(token: String, taskId: String): TaskSnapshot = withContext(Dispatchers.IO) {
        statusInternal(token, taskId)
    }

    private fun statusInternal(token: String, taskId: String): TaskSnapshot {
        val body = JSONObject()
            .put("op", "status")
            .put("deviceId", deviceIdProvider())
            .put("taskId", taskId)

        return taskFrom(requireOk(signedPost(token, body)))
    }

    private fun boundedObjective(text: String): String {
        val base = text.trim().take(3_500)
        val safety = "\n\nExecution safety: keep returned tool data compact. Never include raw payloads larger than needed. For Gmail/email reads use metadata only, exclude message bodies/payloads/attachments, and return at most 3 messages unless the user explicitly asks otherwise."
        return (base + safety).take(4_000)
    }

    private fun signedPost(token: String, payloadObject: JSONObject): JSONObject {
        val deviceId = deviceIdProvider()
        val payload = payloadObject.toString()
        val timestamp = System.currentTimeMillis()
        val nonce = randomNonce()
        val keyHex = sha256Hex(token)
        val signingText = "ICARUS_QUEUE_V1\n$deviceId\n$timestamp\n$nonce\n$payload"
        val signature = hmacSha256Hex(keyHex, signingText)

        val envelope = JSONObject()
            .put("v", 1)
            .put("deviceId", deviceId)
            .put("timestamp", timestamp)
            .put("nonce", nonce)
            .put("payload", payload)
            .put("signature", signature)

        return post(envelope)
    }

    private fun post(body: JSONObject): JSONObject {
        val endpoint = endpointProvider().trim()
        require(endpoint.startsWith("https://")) { "HTTPS backend URL required" }

        val conn = (URL(endpoint).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 15_000
            readTimeout = 60_000
            doOutput = true
            instanceFollowRedirects = true
            setRequestProperty("Content-Type", "application/json; charset=utf-8")
            setRequestProperty("Accept", "application/json")
        }

        conn.outputStream.use {
            it.write(body.toString().toByteArray(StandardCharsets.UTF_8))
        }

        val stream = if (conn.responseCode in 200..299) conn.inputStream else conn.errorStream
        val text = stream?.bufferedReader()?.use { it.readText() } ?: "{}"
        conn.disconnect()
        return JSONObject(text)
    }

    private fun requireOk(root: JSONObject): JSONObject {
        check(root.optBoolean("ok")) {
            root.optString("error", "Icarus request failed")
        }
        return root.optJSONObject("data") ?: JSONObject()
    }

    private fun taskFrom(data: JSONObject): TaskSnapshot {
        val rawResult = data.opt("result")
        val resultText = when (rawResult) {
            null, JSONObject.NULL -> ""
            is JSONObject -> rawResult.toString(2).take(16_000)
            else -> rawResult.toString().take(16_000)
        }

        return TaskSnapshot(
            taskId = data.optString("task_id"),
            status = data.optString("status", "UNKNOWN"),
            objective = data.optString("objective"),
            evidence = data.optString("evidence_ref").take(8_000),
            resultText = resultText
        )
    }

    private fun isActive(status: String): Boolean =
        status.uppercase() in setOf(
            "QUEUED",
            "INSPECTING",
            "REASONING",
            "EXECUTING",
            "VERIFYING",
            "PENDING_AUTH",
            "WAITING_REASONING_CAPACITY"
        )

    private fun randomNonce(): String {
        val bytes = ByteArray(24)
        SecureRandom().nextBytes(bytes)
        return android.util.Base64.encodeToString(
            bytes,
            android.util.Base64.URL_SAFE or android.util.Base64.NO_WRAP or android.util.Base64.NO_PADDING
        )
    }

    private fun sha256Hex(value: String): String =
        MessageDigest.getInstance("SHA-256")
            .digest(value.toByteArray(StandardCharsets.UTF_8))
            .joinToString("") { "%02x".format(it) }

    private fun hmacSha256Hex(keyHex: String, text: String): String {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(
            SecretKeySpec(
                keyHex.toByteArray(StandardCharsets.UTF_8),
                "HmacSHA256"
            )
        )
        return mac.doFinal(text.toByteArray(StandardCharsets.UTF_8))
            .joinToString("") { "%02x".format(it) }
    }
}
