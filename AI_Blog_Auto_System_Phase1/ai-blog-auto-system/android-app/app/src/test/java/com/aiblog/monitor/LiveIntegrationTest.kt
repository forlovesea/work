package com.aiblog.monitor

import android.app.Application
import android.app.NotificationManager
import android.content.Context
import androidx.test.core.app.ApplicationProvider
import okhttp3.*
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.Shadows.shadowOf
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28], application = Application::class)
class LiveIntegrationTest {
    @Test fun windowsPackageThroughRealServerToAndroid() {
        val origin = System.getenv("BLOG_INTEGRATION_URL")
        assumeTrue("Opt in using tests/integration_live.py", origin != null)
        require(java.net.URI(origin!!).host == "127.0.0.1")
        val client = HttpApi.httpClient()
        val paired = HttpApi.pair(origin, System.getenv("BLOG_INTEGRATION_CODE"), "Robolectric integration", client)
        val api = HttpApi(origin, paired.getString("token"), client)
        val context = ApplicationProvider.getApplicationContext<Context>()
        val db = LocalStore(context)
        val scope = "live-" + paired.getString("device_id")
        try {
            val rows = api.events(0)
            assertTrue(rows.any { it.type == "NAVER_LOGIN_EXPIRED" })
            assertTrue(rows.any { it.type == "PUBLISH_FAILED" })
            assertTrue(rows.any { it.type == "PACKAGE_UPLOAD_SUCCESS" })
            val json = JSONArray(api.packages())
            val item = (0 until json.length()).map { ContentPackage.parse(json.getJSONObject(it)) }
                .single { it.id == System.getenv("BLOG_INTEGRATION_PACKAGE") }
            val zip = api.download(item.id, "zip")
            assertEquals(item.sha256, sha256(zip))
            val preview = PreviewBuilder.build(zip, item)
            assertEquals(3, "data:image/png;base64,".toRegex().findAll(preview.html).count())
            assertTrue(preview.html.indexOf("image-first") < preview.html.indexOf("image-second"))
            assertTrue(preview.html.indexOf("image-second") < preview.html.indexOf("image-third"))
            assertTrue(api.download(item.id, "docx").size > 1000)
            assertTrue(clipboardContent(preview).clip.getItemAt(0).text.contains("통합"))
            val gotCompletion = CountDownLatch(1)
            val cursor = rows.last().sequence
            val ws = client.newWebSocket(api.request("/api/v1/events/ws?after=$cursor").build(), object : WebSocketListener() {
                override fun onMessage(webSocket: WebSocket, text: String) {
                    if (text.contains("MANUAL_PUBLISH_COMPLETED")) gotCompletion.countDown()
                }
            })
            assertTrue(api.registerPush("integration-fake-fcm-token"))
            api.completeManual(item.id, "https://blog.naver.com/integration/123")
            api.completeManual(item.id, "https://blog.naver.com/integration/123")
            assertTrue("Real WebSocket completion", gotCompletion.await(15, TimeUnit.SECONDS))
            ws.cancel()
            val completion = api.events(cursor).single { it.type == "MANUAL_PUBLISH_COMPLETED" }
            assertFalse(JSONObject(completion.payload).getBoolean("verified"))
            assertEquals("수동 발행 완료 (사용자 신고)", dashboard(listOf(completion)).publication)
            // Read the data payload captured at the server FCM adapter boundary.
            val pushFile = File(System.getenv("BLOG_INTEGRATION_PUSH_FILE"))
            val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(15)
            var delivered: JSONObject? = null
            while (System.nanoTime() < deadline && delivered == null) {
                if (pushFile.exists()) pushFile.readLines().forEach { line ->
                    runCatching { JSONObject(line) }.getOrNull()?.let {
                        if (it.optString("event_id") == completion.id) delivered = it
                    }
                }
                if (delivered == null) Thread.sleep(100)
            }
            assertNotNull("Server push adapter emitted completion", delivered)
            Notifications.show(context, db, scope, delivered!!.getString("event_id"), eventLabel(delivered!!.getString("event_type")))
            Notifications.show(context, db, scope, delivered!!.getString("event_id"), "duplicate")
            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            assertEquals(1, shadowOf(manager).allNotifications.size)
        } finally {
            db.close(); client.connectionPool.evictAll(); client.dispatcher.executorService.shutdown()
        }
    }
}
