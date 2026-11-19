package com.aiblog.monitor

import android.Manifest
import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.*
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import java.util.UUID
import java.util.concurrent.TimeUnit

class MonitorApp : Application() {
    val repository by lazy { MonitorRepository(this) }
    override fun onCreate() {
        super.onCreate()
        Notifications.channel(this)
        BackgroundSync.schedule(this)
        getSystemService(ConnectivityManager::class.java).registerDefaultNetworkCallback(object : ConnectivityManager.NetworkCallback() {
            override fun onCapabilitiesChanged(network: Network, capabilities: NetworkCapabilities) { repository.networkChanged() }
            override fun onLost(network: Network) { repository.networkChanged() }
        })
        if (FirebaseApp.getApps(this).isNotEmpty()) {
            FirebaseMessaging.getInstance().token.addOnSuccessListener { repository.saveFcmToken(it) }
        }
    }
}

object Notifications {
    const val CHANNEL = "blog-events"
    fun channel(context: Context) {
        context.getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(CHANNEL, "블로그 운영 알림", NotificationManager.IMPORTANCE_DEFAULT))
    }
    fun show(context: Context, store: LocalStore, scope: String, id: String, text: String): Boolean {
        if (android.os.Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return false
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) return false
        if (!store.markNotification(scope, id)) return false
        channel(context)
        val pending = PendingIntent.getActivity(context, 0, Intent(context, MainActivity::class.java), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val notification = NotificationCompat.Builder(context, CHANNEL).setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("AI Blog Monitor").setContentText(text.take(150)).setContentIntent(pending)
            .setAutoCancel(true).setVisibility(NotificationCompat.VISIBILITY_PRIVATE).build()
        NotificationManagerCompat.from(context).notify(id.hashCode(), notification)
        return true
    }
}

class MonitorMessagingService : FirebaseMessagingService() {
    override fun onNewToken(token: String) { (application as MonitorApp).repository.saveFcmToken(token) }
    override fun onMessageReceived(message: RemoteMessage) {
        val repo = (application as MonitorApp).repository
        PushHints.receive(this, repo, message.data) { BackgroundSync.enqueue(this) }
    }
}

object PushHints {
    fun receive(context: Context, repo: MonitorRepository, data: Map<String, String>, enqueue: () -> Unit) {
        if (repo.settings.mock || !repo.settings.configured) return
        val id = data["event_id"] ?: return
        if (runCatching { UUID.fromString(id) }.isFailure) return
        Notifications.show(context, repo.store, repo.settings.scope, id, eventLabel(data["event_type"].orEmpty()))
        // Push is only a hint: never advance the durable event cursor from FCM data.
        enqueue()
    }
}

class SyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val repo = (applicationContext as MonitorApp).repository
        if (repo.settings.mock || !repo.settings.configured) return Result.success()
        return try { repo.sync(); Result.success() }
        catch (e: Exception) {
            repo.report(e)
            if (e is ApiFailure && e.status == 401) Result.failure() else Result.retry()
        }
    }
}

object BackgroundSync {
    private fun constraints() = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()
    fun schedule(context: Context) {
        val request = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES).setConstraints(constraints()).build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork("blog-periodic", ExistingPeriodicWorkPolicy.KEEP, request)
    }
    fun enqueue(context: Context) {
        val request = OneTimeWorkRequestBuilder<SyncWorker>().setConstraints(constraints())
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.SECONDS).build()
        WorkManager.getInstance(context).enqueueUniqueWork("blog-reconnect", ExistingWorkPolicy.KEEP, request)
    }
}
