# kotlinx.serialization DTOs sent over the wire - keep names and generated serializers
-keep,includedescriptorclasses class com.zhk.shelfsense.data.remote.**$$serializer { *; }
-keepclassmembers class com.zhk.shelfsense.data.remote.** {
    *** Companion;
    kotlinx.serialization.KSerializer serializer(...);
}
-keep @kotlinx.serialization.Serializable class com.zhk.shelfsense.data.remote.** { *; }

# Retrofit service interface (reflection on annotations)
-keep interface com.zhk.shelfsense.data.remote.ScanApi { *; }

# WorkManager instantiates workers reflectively by class name
-keep class com.zhk.shelfsense.data.SyncWorker { <init>(...); }
