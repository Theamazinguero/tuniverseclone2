package com.tuniverse.demo.data.api

import com.tuniverse.demo.BuildConfig
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

object RetrofitInstance {
    private const val FALLBACK = "http://10.0.2.2:8000/" // emulator default
    private val baseUrl = BuildConfig.BASE_URL ?: FALLBACK

    val api: TuniverseApi by lazy {
        Retrofit.Builder()
            .baseUrl(baseUrl)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(TuniverseApi::class.java)
    }
}
