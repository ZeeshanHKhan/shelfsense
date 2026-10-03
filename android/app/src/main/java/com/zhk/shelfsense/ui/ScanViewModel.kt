package com.zhk.shelfsense.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.zhk.shelfsense.R
import com.zhk.shelfsense.data.ScanRepository
import com.zhk.shelfsense.data.SyncWorker
import com.zhk.shelfsense.data.local.ScanEntity
import com.zhk.shelfsense.scan.LabelReading
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class LiveReadingState(
    val cameraBarcode: String? = null,
    val hardwareBarcode: String? = null,
    val priceCents: Int? = null,
    val rawPriceText: String = "",
    val confidence: Float = 0f,
    val messageRes: Int? = null,
) {
    val barcode: String? get() = hardwareBarcode ?: cameraBarcode
    val canCapture: Boolean get() = barcode != null && priceCents != null
}

class ScanViewModel(
    application: Application,
    private val repository: ScanRepository,
) : AndroidViewModel(application) {

    private val _live = MutableStateFlow(LiveReadingState())
    val live: StateFlow<LiveReadingState> = _live.asStateFlow()

    // WhileSubscribed(5_000): keeps Room queries alive across rotation, stops them when the screen is gone.
    val recent: StateFlow<List<ScanEntity>> =
        repository.recent.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val pendingCount: StateFlow<Int> =
        repository.pendingCount.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), 0)

    fun onCameraReading(reading: LabelReading) {
        _live.update { state ->
            state.copy(
                cameraBarcode = reading.barcode ?: state.cameraBarcode,
                priceCents = reading.priceCents ?: state.priceCents,
                rawPriceText = if (reading.priceCents != null) reading.rawPriceText else state.rawPriceText,
                confidence = if (reading.priceCents != null) reading.confidence else state.confidence,
            )
        }
    }

    fun onHardwareBarcode(barcode: String) {
        _live.update { it.copy(hardwareBarcode = barcode, messageRes = null) }
    }

    fun capture() {
        val snapshot = _live.value
        val barcode = snapshot.barcode
        if (barcode == null || snapshot.priceCents == null) {
            _live.update { it.copy(messageRes = R.string.capture_incomplete) }
            return
        }
        // viewModelScope runs on Dispatchers.Main.immediate; Room's suspend DAO moves the insert
        // onto its own IO executor, so there is no need to switch dispatchers here.
        viewModelScope.launch {
            repository.enqueue(barcode, snapshot.priceCents, snapshot.rawPriceText, snapshot.confidence)
            SyncWorker.schedule(getApplication())
            _live.value = LiveReadingState(messageRes = R.string.captured_queued)
        }
    }

    fun syncNow() = SyncWorker.schedule(getApplication())
}
