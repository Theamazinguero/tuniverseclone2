package com.tuniverse.demo.data.models

data class PassportData(
    val user_id: String,
    val total_artists: Int,
    val country_counts: Map<String, Int>,
    val region_percentages: Map<String, Float>,
    val share_link: String?
)
