package com.aistudio.icarus.appsscript

import android.content.Context

class RecoveryStore(context: Context) {
    companion object {
        const val DEFAULT_ENDPOINT = "https://script.google.com/macros/s/AKfycbw7k-w7MVQt81U8vB3tJfLNsa3vvglvl1ANR2eIzsx2YJMJeifn5DrbnVWVy7rxocwJXw/exec"
        const val DEVICE_ID = "8f64655c-9eff-43fd-aba6-c624073995ca"
    }

    private val prefs = context.getSharedPreferences("icarus_recovery_v1", Context.MODE_PRIVATE)

    fun token(): String = prefs.getString("device_token", "") ?: ""
    fun endpoint(): String = prefs.getString("backend_url", DEFAULT_ENDPOINT) ?: DEFAULT_ENDPOINT
    fun saveToken(token: String) {
        prefs.edit().putString("device_token", token.trim()).apply()
    }
    fun clearToken() {
        prefs.edit().remove("device_token").apply()
    }
}
