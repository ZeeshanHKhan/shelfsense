package com.zhk.shelfsense.di

import android.app.Application
import android.os.Build
import androidx.room.Room
import com.zhk.shelfsense.BuildConfig
import com.zhk.shelfsense.data.ScanRepository
import com.zhk.shelfsense.data.local.ScanDatabase
import com.zhk.shelfsense.data.remote.ScanApi
import com.zhk.shelfsense.ui.ScanViewModel
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import org.koin.android.ext.koin.androidContext
import org.koin.core.module.dsl.viewModel
import org.koin.dsl.module
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit

val appModule = module {
    single {
        Room.databaseBuilder(androidContext(), ScanDatabase::class.java, "shelfsense.db").build()
    }
    single { get<ScanDatabase>().scanDao() }

    single {
        OkHttpClient.Builder()
            .connectTimeout(5, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .addInterceptor { chain ->
                chain.proceed(chain.request().newBuilder().header("X-Api-Key", BuildConfig.SERVER_API_KEY).build())
            }
            .build()
    }
    single {
        val json = Json { ignoreUnknownKeys = true }
        Retrofit.Builder()
            .baseUrl(BuildConfig.SERVER_BASE_URL)
            .client(get())
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(ScanApi::class.java)
    }
    single {
        ScanRepository(
            dao = get(),
            api = get(),
            deviceId = "${Build.MANUFACTURER}-${Build.MODEL}".take(64),
            storeId = BuildConfig.STORE_ID,
        )
    }
    // androidContext() is bound as Context. ScanViewModel needs the Application instance.
    viewModel { ScanViewModel(androidContext() as Application, get()) }
}
