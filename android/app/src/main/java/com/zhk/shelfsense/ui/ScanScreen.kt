package com.zhk.shelfsense.ui

import android.Manifest
import android.content.pm.PackageManager
import android.util.Log
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.zhk.shelfsense.R
import com.zhk.shelfsense.data.local.ScanEntity
import com.zhk.shelfsense.data.local.SyncState
import com.zhk.shelfsense.scan.LabelAnalyzer
import com.zhk.shelfsense.scan.LabelReading
import java.text.NumberFormat
import java.util.Locale
import java.util.concurrent.ExecutionException
import java.util.concurrent.Executors

private const val TAG = "ScanScreen"

@Composable
fun ScanScreen(viewModel: ScanViewModel) {
    val context = LocalContext.current
    var hasCamera by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
        )
    }
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        hasCamera = it
    }
    val live by viewModel.live.collectAsStateWithLifecycle()
    val recent by viewModel.recent.collectAsStateWithLifecycle()
    val pending by viewModel.pendingCount.collectAsStateWithLifecycle()

    Scaffold { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(Modifier.fillMaxWidth().height(280.dp)) {
                if (hasCamera) {
                    CameraPreview(onReading = viewModel::onCameraReading, modifier = Modifier.fillMaxSize())
                } else {
                    Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.Center) {
                        Text(stringResource(R.string.camera_permission_rationale))
                        Button(onClick = { permissionLauncher.launch(Manifest.permission.CAMERA) }) {
                            Text(stringResource(R.string.grant_camera))
                        }
                    }
                }
            }

            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp)) {
                    val barcodeText = live.barcode ?: stringResource(R.string.not_detected)
                    val source = if (live.hardwareBarcode != null) " " + stringResource(R.string.hardware_scanner) else ""
                    Text(stringResource(R.string.reading_barcode, barcodeText) + source)
                    Text(stringResource(R.string.reading_price, live.priceCents?.let(::money) ?: stringResource(R.string.not_detected)))
                    Text(stringResource(R.string.reading_confidence, (live.confidence * 100).toInt()))
                }
            }

            val captureDescription = stringResource(R.string.capture_description)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = viewModel::capture,
                    enabled = live.canCapture,
                    modifier = Modifier.semantics { contentDescription = captureDescription },
                ) { Text(stringResource(R.string.capture)) }
                OutlinedButton(onClick = viewModel::syncNow) { Text(stringResource(R.string.sync_now)) }
            }
            live.messageRes?.let { Text(stringResource(it), style = MaterialTheme.typography.bodySmall) }
            Text(stringResource(R.string.pending_count, pending), style = MaterialTheme.typography.bodySmall)

            Text(stringResource(R.string.recent_scans), style = MaterialTheme.typography.titleMedium)
            LazyColumn(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                items(recent, key = { it.clientId }) { scan -> ScanRow(scan) }
            }
        }
    }
}

@Composable
private fun ScanRow(scan: ScanEntity) {
    val (label, color) = when {
        scan.syncState == SyncState.PENDING -> stringResource(R.string.status_pending) to Color.Gray
        scan.syncState == SyncState.REJECTED -> stringResource(R.string.status_rejected) to Color(0xFFF2555A)
        scan.serverStatus == "MATCH" -> stringResource(R.string.status_match) to Color(0xFF3ECF8E)
        scan.serverStatus == "MISMATCH" -> stringResource(R.string.status_mismatch) to Color(0xFFF2555A)
        scan.serverStatus == "UNKNOWN_SKU" -> stringResource(R.string.status_unknown) to Color(0xFFF5A524)
        else -> stringResource(R.string.status_recapture) to Color(0xFF5B8CFF)
    }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(10.dp)) {
            Text(scan.description ?: scan.barcode, style = MaterialTheme.typography.bodyMedium)
            Text(
                "${scan.shelfPriceCents?.let(::money) ?: "—"} → ${scan.expectedPriceCents?.let(::money) ?: "—"}",
                style = MaterialTheme.typography.bodySmall,
            )
            Text(label, color = color, style = MaterialTheme.typography.labelMedium)
        }
    }
}

@Composable
private fun CameraPreview(onReading: (LabelReading) -> Unit, modifier: Modifier) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val previewDescription = stringResource(R.string.camera_preview_description)
    val previewView = remember { PreviewView(context).apply { contentDescription = previewDescription } }

    DisposableEffect(lifecycleOwner) {
        // ML Kit work is kicked off from a single background thread so the UI thread never touches frames.
        val analysisExecutor = Executors.newSingleThreadExecutor()
        val analyzer = LabelAnalyzer(onReading)
        val providerFuture = ProcessCameraProvider.getInstance(context)
        providerFuture.addListener({
            try {
                val provider = providerFuture.get()
                val preview = Preview.Builder().build().also { it.setSurfaceProvider(previewView.surfaceProvider) }
                val analysis = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build()
                    .also { it.setAnalyzer(analysisExecutor, analyzer) }
                provider.unbindAll()
                provider.bindToLifecycle(lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis)
            } catch (e: ExecutionException) {
                Log.e(TAG, "Camera provider failed to initialize", e)
            } catch (e: InterruptedException) {
                Log.e(TAG, "Camera provider init interrupted", e)
            } catch (e: IllegalArgumentException) {
                Log.e(TAG, "No back camera available", e)
            } catch (e: IllegalStateException) {
                Log.e(TAG, "Camera use case binding failed", e)
            }
        }, ContextCompat.getMainExecutor(context))

        onDispose {
            if (providerFuture.isDone) {
                try {
                    providerFuture.get().unbindAll()
                } catch (e: ExecutionException) {
                    Log.w(TAG, "Provider unavailable during dispose", e)
                } catch (e: InterruptedException) {
                    Log.w(TAG, "Interrupted during dispose", e)
                }
            }
            analyzer.close()
            analysisExecutor.shutdown()
        }
    }
    AndroidView(factory = { previewView }, modifier = modifier)
}

private fun money(cents: Int): String = NumberFormat.getCurrencyInstance(Locale.US).format(cents / 100.0)
