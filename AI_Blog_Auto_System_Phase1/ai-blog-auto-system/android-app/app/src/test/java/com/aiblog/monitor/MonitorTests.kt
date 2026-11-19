package com.aiblog.monitor

import android.app.Application
import android.content.Context
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okhttp3.Response
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.After
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.time.Instant
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import java.io.ByteArrayOutputStream
import java.io.IOException

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28], application = Application::class)
class MonitorTests {
    private val repositories = mutableListOf<MonitorRepository>()
    private fun repository() = MonitorRepository(context).also { repositories.add(it) }
    @After fun closeRepositories() = runBlocking { repositories.forEach { it.shutdown() } }
    private val context get() = ApplicationProvider.getApplicationContext<Context>()
    private fun mock() = MockApi(context, Instant.now())
    private fun item(api: MockApi) = ContentPackage.parse(JSONArray(api.packages()).getJSONObject(0))

    @Test fun httpsAndDebugOriginPolicy() {
        assertEquals("https://example.com", validateOrigin("https://example.com/", false))
        assertEquals("http://10.0.2.2:8000", validateOrigin("http://10.0.2.2:8000", true))
        for (url in listOf("http://example.com", "https://user:secret@example.com", "https://example.com/path", "https://example.com?q=1", "file:///secret")) {
            assertThrows(IllegalArgumentException::class.java) { validateOrigin(url, true) }
        }
        assertThrows(IllegalArgumentException::class.java) { validateOrigin("http://10.0.2.2:8000", false) }
    }

    @Test fun expiryBoundaryAndCountdown() {
        val expires = Instant.parse("2026-11-20T00:00:00Z")
        val p = ContentPackage("id", 0, "", "", expires.toString())
        assertFalse(p.expired(expires.minusNanos(1)))
        assertTrue(p.expired(expires))
        assertEquals("남은 시간 01:00:01", p.remaining(expires.minusSeconds(3601)))
        assertTrue(p.copy(deleted = true).expired(expires.minusSeconds(500)))
    }

    @Test fun dashboardSeparatesMockSuccess() {
        val date = Instant.now().toString()
        val rows = listOf("PC_ONLINE", "PUBLISH_SUCCESS", "MOCK_PUBLISH_SUCCESS", "NAVER_LOGIN_EXPIRED", "PUBLISH_FAILED").mapIndexed { i, t -> BlogEvent(i + 1L, "$i", t, date) }
        val status = dashboard(rows.reversed())
        assertEquals(1, status.published)
        assertEquals(1, status.failed)
        assertEquals("ONLINE", status.windows)
        assertEquals("네이버 로그인 만료", status.login)
        assertEquals("발행 실패", status.publication)
    }

    @Test fun sqliteCursorDedupRestartAndScopeIsolation() {
        val store = LocalStore(context)
        val rows = mock().events(0)
        store.apply("server-a", rows); store.apply("server-a", rows)
        assertEquals(4, store.events("server-a").size)
        assertEquals(4L, store.cursor("server-a"))
        store.apply("server-a", listOf(rows.first()))
        assertEquals(4L, store.cursor("server-a"))
        assertEquals(0L, store.cursor("server-b"))
        assertTrue(store.markNotification("server-a", "x"))
        assertFalse(store.markNotification("server-a", "x"))
        store.close()
        val reopened = LocalStore(context)
        try { assertEquals(4L, reopened.cursor("server-a")) } finally { reopened.close() }
    }

    @Test fun mockSyncDownloadAndImageOrderWithoutCredentials() = runBlocking {
        val repo = repository()
        repo.sync()
        assertTrue(repo.state.value.mock)
        assertEquals(4, repo.state.value.events.size)
        val api = mock()
        val item = item(api)
        val preview = PreviewBuilder.build(api.download(item.id, "zip"), item)
        assertTrue(preview.text.contains("수동 발행"))
        val doc = org.jsoup.Jsoup.parse(preview.html)
        assertEquals(3, doc.select("img").size)
        assertTrue(doc.select("img").all { it.attr("src").startsWith("data:image/png;base64,") })
        val zip = java.util.zip.ZipInputStream(api.download(item.id, "zip").inputStream())
        val files = mutableMapOf<String, ByteArray>()
        zip.use { while (true) { val entry = zip.nextEntry ?: break; files[entry.name] = zip.readBytes() } }
        val manifest = JSONObject(files.getValue("manifest.json").toString(Charsets.UTF_8))
        val order = manifest.getJSONArray("image_order")
        doc.select("img").forEachIndexed { i, image ->
            assertArrayEquals(files.getValue(order.getString(i)), java.util.Base64.getDecoder().decode(image.attr("src").substringAfter(',')))
        }
        assertArrayEquals(files.getValue("article.docx"), api.download(item.id, "docx"))
    }

    @Test fun previewRejectsTamperingAndTraversal() {
        val api = mock(); val item = item(api)
        assertThrows(IllegalArgumentException::class.java) { PreviewBuilder.build(byteArrayOf(1, 2), item) }
        val output = ByteArrayOutputStream()
        ZipOutputStream(output).use { zip -> zip.putNextEntry(ZipEntry("../escape.html")); zip.write("bad".toByteArray()); zip.closeEntry() }
        val bytes = output.toByteArray()
        assertThrows(IllegalArgumentException::class.java) { PreviewBuilder.build(bytes, item.copy(sha256 = sha256(bytes))) }
        assertThrows(IllegalArgumentException::class.java) { PreviewBuilder.build(api.download(item.id, "zip"), item.copy(expiresAt = Instant.now().minusSeconds(1).toString())) }
    }

    @Test fun apiHeadersIntegrityAndExpiry() {
        MockWebServer().use { server ->
            val bytes = "download".toByteArray()
            server.enqueue(MockResponse().setBody("download").setHeader("X-Content-SHA256", sha256(bytes)))
            val api = HttpApi(server.url("/").toString().trimEnd('/'), "monitor-token")
            assertArrayEquals(bytes, api.download("99f7d610-d944-4011-a8da-9dcdd88f1120", "zip"))
            assertEquals("monitor-token", server.takeRequest().getHeader("X-Device-Token"))
            server.enqueue(MockResponse().setBody("corrupt").setHeader("X-Content-SHA256", "0".repeat(64)))
            assertThrows(IllegalArgumentException::class.java) { api.download("99f7d610-d944-4011-a8da-9dcdd88f1120", "zip") }
            server.enqueue(MockResponse().setResponseCode(410))
            assertEquals(410, assertThrows(ApiFailure::class.java) { api.download("99f7d610-d944-4011-a8da-9dcdd88f1120", "docx") }.status)
        }
    }

    @Test fun pairingAndCursorRequests() {
        MockWebServer().use { server ->
            server.enqueue(MockResponse().setBody("""{"device_id":"test","token":"secret","expires_at":"later"}"""))
            val origin = server.url("/").toString().trimEnd('/')
            assertEquals("secret", HttpApi.pair(origin, "abc", "Android").getString("token"))
            val request = server.takeRequest()
            assertEquals("/api/v1/pairing/claim", request.path)
            assertEquals("abc", JSONObject(request.body.readUtf8()).getString("code"))
            server.enqueue(MockResponse().setBody("[]"))
            assertTrue(HttpApi(origin, "secret").events(42).isEmpty())
            assertEquals("/api/v1/events?after=42&limit=100", server.takeRequest().path)
        }
    }

    @Test fun websocketUsesHeaderAndResumeCursor() {
        MockWebServer().use { server ->
            server.enqueue(MockResponse().withWebSocketUpgrade(object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) { webSocket.send("""{"type":"heartbeat","cursor":7}""") }
            }))
            val api = HttpApi(server.url("/").toString().trimEnd('/'), "secret")
            val received = CountDownLatch(1)
            val socket = api.client.newWebSocket(api.request("/api/v1/events/ws?after=7").build(), object : WebSocketListener() {
                override fun onMessage(webSocket: WebSocket, text: String) { if (JSONObject(text).getLong("cursor") == 7L) received.countDown() }
            })
            assertTrue(received.await(5, TimeUnit.SECONDS))
            val request = server.takeRequest()
            assertEquals("secret", request.getHeader("X-Device-Token"))
            assertEquals("/api/v1/events/ws?after=7", request.path)
            socket.cancel()
            api.client.dispatcher.executorService.shutdown()
        }
    }

    @Test fun pushHintsDoNotSkipUnfetchedEvents() {
        val repo = repository()
        repo.settings.mock = false; repo.settings.configured = true
        repo.settings.origin = "https://example.com"; repo.settings.deviceId = "paired"
        var enqueued = 0
        val data = mapOf("event_id" to "d0000000-0000-4000-8000-000000000001", "event_type" to "PUBLISH_FAILED", "sequence" to "999")
        PushHints.receive(context, repo, data) { enqueued++ }
        PushHints.receive(context, repo, data) { enqueued++ }
        assertEquals(2, enqueued)
        assertEquals(0L, repo.store.cursor(repo.settings.scope))
        assertTrue(repo.store.events(repo.settings.scope).isEmpty())
        val manager = context.getSystemService(android.app.NotificationManager::class.java)
        assertEquals(1, org.robolectric.Shadows.shadowOf(manager).size())
    }

    @Test fun htmlPreviewRemovesScriptsHandlersAndExternalResources() {
        val api = mock(); val item = item(api)
        val files = linkedMapOf<String, ByteArray>()
        java.util.zip.ZipInputStream(api.download(item.id, "zip").inputStream()).use { zip ->
            while (true) { val entry = zip.nextEntry ?: break; files[entry.name] = zip.readBytes() }
        }
        val injection = "<script>alert('bad')</script><iframe src='https://evil.example/'></iframe><img src='https://evil.example/p.png'><p onclick='alert(1)'>safe</p>"
        files["index.html"] = files.getValue("index.html").toString(Charsets.UTF_8).replace("</body>", "$injection</body>").toByteArray()
        val manifest = JSONObject(files.getValue("manifest.json").toString(Charsets.UTF_8))
        val entries = manifest.getJSONArray("files")
        for (i in 0 until entries.length()) {
            val row = entries.getJSONObject(i)
            if (row.getString("path") == "index.html") row.put("size", files.getValue("index.html").size).put("sha256", sha256(files.getValue("index.html")))
        }
        files["manifest.json"] = manifest.toString().toByteArray()
        val output = ByteArrayOutputStream()
        ZipOutputStream(output).use { zip -> files.forEach { (name, bytes) -> zip.putNextEntry(ZipEntry(name)); zip.write(bytes); zip.closeEntry() } }
        val bytes = output.toByteArray()
        val preview = PreviewBuilder.build(bytes, item.copy(sha256 = sha256(bytes)))
        assertFalse(preview.html.contains("<script"))
        assertFalse(preview.html.contains("onclick"))
        assertFalse(preview.html.contains("evil.example"))
        assertTrue(preview.html.contains("safe"))
    }

    @Test fun offlineFailureKeepsHistoryAndCursor() = runBlocking {
        val repo = repository()
        repo.sync()
        val before = repo.store.cursor("mock")
        repo.settings.mock = false
        assertThrows(IOException::class.java) { runBlocking { repo.sync() } }
        assertEquals(before, repo.store.cursor("mock"))
        repo.settings.mock = true
        repo.sync()
        assertEquals(4, repo.state.value.events.size)
    }

    @Test fun clipboardKeepsWholeTextWhenImagesExceedBinderBudget() {
        val text = "전체 본문을 자르지 않습니다."
        val preview = Preview("id", "제목", "<p>$text</p><img src='data:image/png;base64,${"a".repeat(300000)}'>", text, Instant.now().plusSeconds(300).toString())
        val content = clipboardContent(preview)
        assertEquals(text, content.clip.getItemAt(0).text.toString())
        assertFalse(content.clip.getItemAt(0).htmlText.contains("data:image"))
        assertTrue(content.message.contains("제외"))
        assertThrows(IllegalArgumentException::class.java) { clipboardContent(preview.copy(text = "x".repeat(300000))) }
    }

    @Test fun webViewAllowsInlinePngButBlocksExternalAndFileRequests() {
        fun request(value: String) = object : android.webkit.WebResourceRequest {
            override fun getUrl() = android.net.Uri.parse(value)
            override fun isForMainFrame() = false
            override fun isRedirect() = false
            override fun hasGesture() = false
            override fun getMethod() = "GET"
            override fun getRequestHeaders() = mutableMapOf<String, String>()
        }
        val client = SafePreviewClient()
        assertNull(client.shouldInterceptRequest(null, request("data:image/png;base64,iVBORw0KGgo=")))
        for (url in listOf("https://evil.example/x.png", "file:///secret", "content://private", "data:text/html;base64,eA==")) {
            assertNotNull(client.shouldInterceptRequest(null, request(url)))
            assertTrue(client.shouldOverrideUrlLoading(null, request(url)))
        }
    }
}
