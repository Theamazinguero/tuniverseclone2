package com.tuniverse.demo.data.repo

import com.tuniverse.demo.data.api.RetrofitInstance
import com.tuniverse.demo.data.models.PassportData
import retrofit2.HttpException

class TuniverseRepo {
    suspend fun fetchPassport(userId: String): Result<PassportData> {
        return try {
            val res = RetrofitInstance.api.getDemoPassport(userId)
            if (res.isSuccessful && res.body() != null) {
                Result.success(res.body()!!)
            } else {
                Result.failure(HttpException(res))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
