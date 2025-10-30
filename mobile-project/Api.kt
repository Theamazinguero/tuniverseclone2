package com.tuniverse.web

import kotlinx.coroutines.await
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.decodeFromDynamic
import kotlinx.browser.window

object Api {
    // Change this if you host elsewhere
    private const val BASE = "http://127.0.0.1:8000"

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
    }

    suspend fun fetchPassport(userId: String): PassportData {
        val res = window.fetch("$BASE/demo_passport/${encodeURIComponent(userId)}").await()
        if (!res.ok) error("HTTP ${res.status}")
        val dyn = res.json().await()
        return json.decodeFromDynamic(dyn)
    }

    private fun encodeURIComponent(s: String): String =
        js("encodeURIComponent")(s) as String
}
