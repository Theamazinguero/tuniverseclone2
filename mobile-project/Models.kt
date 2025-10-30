package com.tuniverse.web

@kotlin.js.ExperimentalJsExport
@JsExport
data class PassportData(
    val user_id: String,
    val total_artists: Int,
    val country_counts: dynamic,        // Map<String, Int> decoded from JSON
    val region_percentages: dynamic,    // Map<String, Float>
    val share_link: String? = null
)
