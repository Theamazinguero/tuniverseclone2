package com.tuniverse.web

import kotlinx.browser.document
import kotlinx.coroutines.MainScope
import kotlinx.coroutines.launch
import org.w3c.dom.HTMLButtonElement
import org.w3c.dom.HTMLInputElement
import org.w3c.dom.HTMLPreElement

private val scope = MainScope()

fun main() {
    val input = document.getElementById("userId") as HTMLInputElement
    val btn = document.getElementById("go") as HTMLButtonElement
    val out = document.getElementById("out") as HTMLPreElement

    btn.onclick = {
        val userId = (input.value ?: "").ifBlank { "demo_user" }
        out.textContent = "Loading..."
        scope.launch {
            try {
                val data = Api.fetchPassport(userId)
                val sb = StringBuilder()
                sb.appendLine("User: ${data.user_id}")
                sb.appendLine("Total artists: ${data.total_artists}")
                sb.appendLine("Countries:")
                // dynamic maps from JSON: iterate keys
                val cc = data.country_counts as dynamic
                js("Object.keys")(cc).unsafeCast<Array<String>>().forEach { k ->
                    val v = cc[k] as Int
                    sb.appendLine("• $k: $v")
                }
                sb.appendLine("Regions:")
                val rp = data.region_percentages as dynamic
                js("Object.keys")(rp).unsafeCast<Array<String>>().forEach { k ->
                    val v = rp[k] as Double
                    sb.appendLine("• $k: ${(v * 100).toInt()}%")
                }
                data.share_link?.let { sb.appendLine("Share: $it") }
                out.textContent = sb.toString()
            } catch (e: dynamic) {
                out.textContent = "Error: ${e?.message ?: e.toString()}"
            }
        }
        null
    }
}
