package com.zhk.shelfsense.data.remote

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import retrofit2.http.Body
import retrofit2.http.POST

@Serializable
data class ScanDto(
    @SerialName("client_id") val clientId: String,
    @SerialName("device_id") val deviceId: String,
    @SerialName("store_id") val storeId: String,
    @SerialName("barcode") val barcode: String,
    @SerialName("shelf_price_cents") val shelfPriceCents: Int?,
    @SerialName("ocr_raw_text") val ocrRawText: String,
    @SerialName("ocr_confidence") val ocrConfidence: Float,
    @SerialName("captured_at") val capturedAt: String,
)

@Serializable
data class ScanBatchRequest(@SerialName("scans") val scans: List<ScanDto>)

@Serializable
data class ScanResultDto(
    @SerialName("client_id") val clientId: String,
    @SerialName("status") val status: String,
    @SerialName("expected_price_cents") val expectedPriceCents: Int? = null,
    @SerialName("description") val description: String? = null,
    @SerialName("duplicate") val duplicate: Boolean,
)

@Serializable
data class ScanBatchResponse(@SerialName("results") val results: List<ScanResultDto>)

interface ScanApi {
    @POST("api/v1/scans")
    suspend fun submit(@Body request: ScanBatchRequest): ScanBatchResponse
}
