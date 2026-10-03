package com.zhk.shelfsense.scan

import androidx.annotation.OptIn
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import java.io.Closeable
import java.util.concurrent.atomic.AtomicBoolean

data class LabelReading(
    val barcode: String?,
    val priceCents: Int?,
    val rawPriceText: String,
    val confidence: Float,
)

/**
 * Runs barcode detection and text recognition on the same frame, fully on-device.
 * No image ever leaves the handheld; only the extracted barcode + price are synced.
 */
class LabelAnalyzer(private val onReading: (LabelReading) -> Unit) : ImageAnalysis.Analyzer, Closeable {

    private val barcodeScanner = BarcodeScanning.getClient(
        BarcodeScannerOptions.Builder()
            .setBarcodeFormats(Barcode.FORMAT_UPC_A, Barcode.FORMAT_EAN_13, Barcode.FORMAT_EAN_8, Barcode.FORMAT_UPC_E)
            .build()
    )
    private val textRecognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
    private val busy = AtomicBoolean(false)

    @OptIn(ExperimentalGetImage::class)
    override fun analyze(imageProxy: ImageProxy) {
        val mediaImage = imageProxy.image
        if (mediaImage == null || !busy.compareAndSet(false, true)) {
            imageProxy.close()
            return
        }
        val input = InputImage.fromMediaImage(mediaImage, imageProxy.imageInfo.rotationDegrees)
        val barcodeTask = barcodeScanner.process(input)
        val textTask = textRecognizer.process(input)

        Tasks.whenAllComplete(barcodeTask, textTask).addOnCompleteListener {
            val barcode = barcodeTask.takeIf { it.isSuccessful }?.result
                ?.firstNotNullOfOrNull { it.rawValue?.takeIf { value -> value.matches(DIGITS_8_TO_14) } }
            val price = textTask.takeIf { it.isSuccessful }?.result?.let { text ->
                PriceParser.bestPrice(
                    text.textBlocks.flatMap { block ->
                        block.lines.map { line ->
                            PriceCandidate(line.text, line.boundingBox?.height() ?: 0, line.confidence)
                        }
                    }
                )
            }
            if (barcode != null || price != null) {
                onReading(
                    LabelReading(
                        barcode = barcode,
                        priceCents = price?.cents,
                        rawPriceText = price?.rawText.orEmpty(),
                        confidence = price?.confidence ?: 0f,
                    )
                )
            }
            imageProxy.close()
            busy.set(false)
        }
    }

    override fun close() {
        barcodeScanner.close()
        textRecognizer.close()
    }

    private companion object {
        val DIGITS_8_TO_14 = Regex("^\\d{8,14}$")
    }
}
