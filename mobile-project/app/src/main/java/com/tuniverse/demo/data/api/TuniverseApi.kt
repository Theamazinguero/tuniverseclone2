package com.tuniverse.demo.data.api

import com.tuniverse.demo.data.models.PassportData
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Path

interface TuniverseApi {
    @GET("demo_passport/{user_id}")
    suspend fun getDemoPassport(@Path("user_id") userId: String): Response<PassportData>
}
