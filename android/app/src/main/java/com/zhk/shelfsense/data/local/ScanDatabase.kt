package com.zhk.shelfsense.data.local

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase
import androidx.room.TypeConverter
import androidx.room.TypeConverters
import kotlinx.coroutines.flow.Flow

enum class SyncState { PENDING, SYNCED, REJECTED }

class SyncStateConverter {
    @TypeConverter fun fromState(value: SyncState): String = value.name
    @TypeConverter fun toState(value: String): SyncState = SyncState.valueOf(value)
}

@Entity(tableName = "scans")
data class ScanEntity(
    @PrimaryKey val clientId: String,
    val barcode: String,
    val shelfPriceCents: Int?,
    val ocrRawText: String,
    val ocrConfidence: Float,
    val capturedAtMillis: Long,
    val syncState: SyncState = SyncState.PENDING,
    val serverStatus: String? = null,
    val expectedPriceCents: Int? = null,
    val description: String? = null,
)

@Dao
interface ScanDao {
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insert(scan: ScanEntity)

    @Query("SELECT * FROM scans WHERE syncState = 'PENDING' ORDER BY capturedAtMillis LIMIT :limit")
    suspend fun pending(limit: Int): List<ScanEntity>

    @Query(
        """UPDATE scans SET syncState = :state, serverStatus = :serverStatus,
           expectedPriceCents = :expectedPriceCents, description = :description
           WHERE clientId = :clientId"""
    )
    suspend fun markResult(
        clientId: String,
        state: SyncState,
        serverStatus: String?,
        expectedPriceCents: Int?,
        description: String?,
    )

    @Query("UPDATE scans SET syncState = 'REJECTED' WHERE clientId IN (:clientIds)")
    suspend fun markRejected(clientIds: List<String>)

    @Query("SELECT * FROM scans ORDER BY capturedAtMillis DESC LIMIT 20")
    fun observeRecent(): Flow<List<ScanEntity>>

    @Query("SELECT COUNT(*) FROM scans WHERE syncState = 'PENDING'")
    fun observePendingCount(): Flow<Int>
}

@Database(entities = [ScanEntity::class], version = 1, exportSchema = false)
@TypeConverters(SyncStateConverter::class)
abstract class ScanDatabase : RoomDatabase() {
    abstract fun scanDao(): ScanDao
}
