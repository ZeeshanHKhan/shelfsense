package com.zhk.shelfsense

import android.app.Application
import com.zhk.shelfsense.di.appModule
import com.zhk.shelfsense.scan.HardwareScanner
import org.koin.android.ext.koin.androidContext
import org.koin.core.context.startKoin

class ShelfSenseApp : Application() {
    override fun onCreate() {
        super.onCreate()
        startKoin {
            androidContext(this@ShelfSenseApp)
            modules(appModule)
        }
        HardwareScanner.ensureProfile(this)
    }
}
