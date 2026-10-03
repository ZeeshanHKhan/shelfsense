package com.zhk.shelfsense.data

import com.zhk.shelfsense.data.local.ScanDao
import com.zhk.shelfsense.data.local.ScanEntity
import com.zhk.shelfsense.data.local.SyncState
import com.zhk.shelfsense.data.remote.ScanApi
import com.zhk.shelfsense.data.remote.ScanBatchRequest
import com.zhk.shelfsense.data.remote.ScanDto
import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.SerializationException
import retrofit2.HttpException
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.UUID

sealed interface SyncOutcome {
    data object Done : SyncOutcome
    data object RetryLater : SyncOutcome
    data class Rejected(val httpCode: Int) : SyncOutcome
}

class ScanRepository(
    private val dao: ScanDao,
    private val api: ScanApi,
    private val deviceId: String,
    private val storeId: String,
) {
    val recent: Flow<List<ScanEntity>> = dao.observeRecent()
    val pendingCount: Flow<Int> = dao.observePendingCount()

    suspend fun enqueue(barcode: String, priceCents: Int?, rawText: String, confidence: Float) {
        dao.insert(
            ScanEntity(
                clientId = UUID.randomUUID().toString(),
                barcode = barcode,
                shelfPriceCents = priceCents,
                ocrRawText = rawText.take(MAX_RAW_TEXT),
                ocrConfidence = confidence.coerceIn(0f, 1f),
                capturedAtMillis = System.currentTimeMillis(),
            )
        )
    }

    /** Drains the local queue in batches. Safe to retry: the server dedupes on clientId. */
    suspend fun syncPending(): SyncOutcome {
        while (true) {
            val batch = dao.pending(BATCH_SIZE)
            if (batch.isEmpty()) return SyncOutcome.Done
            val response = try {
                api.submit(ScanBatchRequest(batch.map { it.toDto() }))
            } catch (e: IOException) {
                return SyncOutcome.RetryLater
            } catch (e: HttpException) {
                if (e.code() >= 500) return SyncOutcome.RetryLater
                dao.markRejected(batch.map { it.clientId })
                return SyncOutcome.Rejected(e.code())
            } catch (e: SerializationException) {
                return SyncOutcome.RetryLater
            }
            response.results.forEach { result ->
                dao.markResult(
                    clientId = result.clientId,
                    state = SyncState.SYNCED,
                    serverStatus = result.status,
                    expectedPriceCents = result.expectedPriceCents,
                    description = result.description,
                )
            }
        }
    }

    private fun ScanEntity.toDto() = ScanDto(
        clientId = clientId,
        deviceId = deviceId,
        storeId = storeId,
        barcode = barcode,
        shelfPriceCents = shelfPriceCents,
        ocrRawText = ocrRawText,
        ocrConfidence = ocrConfidence,
        capturedAt = isoUtc(capturedAtMillis),
    )

    private fun isoUtc(millis: Long): String =
        SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US)
            .apply { timeZone = TimeZone.getTimeZone("UTC") }
            .format(Date(millis))

    private companion object {
        const val BATCH_SIZE = 50
        const val MAX_RAW_TEXT = 500
    }
}
