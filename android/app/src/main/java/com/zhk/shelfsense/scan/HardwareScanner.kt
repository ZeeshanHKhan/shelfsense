package com.zhk.shelfsense.scan

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Parcelable

/**
 * On a rugged handheld the imager is faster than the camera for barcodes.
 * The vendor scanner app delivers scans as broadcast intents; camera OCR still reads the printed price.
 * On a regular phone nothing listens for these intents, so the camera path is used.
 */
object HardwareScanner {
    const val SCAN_ACTION = "com.zhk.shelfsense.SCAN"
    private const val PROFILE_NAME = "ShelfSense"
    private const val API_ACTION = "com.symbol.datawedge.api.ACTION"
    private const val EXTRA_SET_CONFIG = "com.symbol.datawedge.api.SET_CONFIG"
    private const val EXTRA_DATA_STRING = "com.symbol.datawedge.data_string"
    private val DIGITS_8_TO_14 = Regex("^\\d{8,14}$")

    /** Creates the scanner profile on first launch so field techs never configure devices by hand. */
    fun ensureProfile(context: Context) {
        val intentPlugin = Bundle().apply {
            putString("PLUGIN_NAME", "INTENT")
            putString("RESET_CONFIG", "true")
            putBundle("PARAM_LIST", Bundle().apply {
                putString("intent_output_enabled", "true")
                putString("intent_action", SCAN_ACTION)
                putString("intent_delivery", "2")
            })
        }
        val keystrokePlugin = Bundle().apply {
            putString("PLUGIN_NAME", "KEYSTROKE")
            putString("RESET_CONFIG", "true")
            putBundle("PARAM_LIST", Bundle().apply { putString("keystroke_output_enabled", "false") })
        }
        val app = Bundle().apply {
            putString("PACKAGE_NAME", context.packageName)
            putStringArray("ACTIVITY_LIST", arrayOf("*"))
        }
        val profile = Bundle().apply {
            putString("PROFILE_NAME", PROFILE_NAME)
            putString("PROFILE_ENABLED", "true")
            putString("CONFIG_MODE", "CREATE_IF_NOT_EXIST")
            putParcelableArray("APP_LIST", arrayOf<Parcelable>(app))
            putParcelableArrayList("PLUGIN_CONFIG", arrayListOf(intentPlugin, keystrokePlugin))
        }
        context.sendBroadcast(Intent(API_ACTION).putExtra(EXTRA_SET_CONFIG, profile))
    }

    class Receiver(private val onBarcode: (String) -> Unit) : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            if (intent.action != SCAN_ACTION) return
            intent.getStringExtra(EXTRA_DATA_STRING)
                ?.trim()
                ?.takeIf { it.matches(DIGITS_8_TO_14) }
                ?.let(onBarcode)
        }
    }
}
