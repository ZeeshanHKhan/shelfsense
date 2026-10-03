package com.zhk.shelfsense.ui

import android.content.IntentFilter
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.core.content.ContextCompat
import com.zhk.shelfsense.scan.HardwareScanner
import org.koin.androidx.viewmodel.ext.android.viewModel

class MainActivity : ComponentActivity() {

    private val viewModel: ScanViewModel by viewModel()
    private val hardwareScanReceiver = HardwareScanner.Receiver { barcode -> viewModel.onHardwareBarcode(barcode) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = darkColorScheme()) {
                ScanScreen(viewModel)
            }
        }
    }

    override fun onStart() {
        super.onStart()
        // Exported because the hardware scanner is a separate system app. Payload is validated as 8-14 digits.
        ContextCompat.registerReceiver(
            this,
            hardwareScanReceiver,
            IntentFilter(HardwareScanner.SCAN_ACTION),
            ContextCompat.RECEIVER_EXPORTED,
        )
    }

    override fun onStop() {
        unregisterReceiver(hardwareScanReceiver)
        super.onStop()
    }
}
