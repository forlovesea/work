package com.aiblog.monitor

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.time.Instant
import java.util.concurrent.atomic.AtomicLong

data class MonitorState(
    val events: List<BlogEvent> = emptyList(), val packages: List<ContentPackage> = emptyList(),
    val connected: Boolean = false, val busy: Boolean = false, val message: String = "",
    val lastSync: String = "", val preview: Preview? = null, val download: File? = null,
    val mock: Boolean = true, val configured: Boolean = false, val pushStatus: String = "Firebase 설정 없음 · Mock 사용 가능"
)

class MonitorRepository(private val context: Context, val settings: Settings = Settings(context),
                        val store: LocalStore = LocalStore(context), private val vault: Vault = Vault(context)) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val syncMutex = Mutex()
    private val actionMutex = Mutex()
    private val httpClient = HttpApi.httpClient()
    private val mutable = MutableStateFlow(MonitorState(mock = settings.mock, configured = settings.configured))
    val state = mutable.asStateFlow()
    private val mockApi = MockApi(context, Instant.ofEpochMilli(settings.mockCreated))
    @Volatile private var foreground = false
    private var socket: WebSocket? = null
    private var reconnectJob: Job? = null
    private val generation = AtomicLong()
    private var attempt = 0
    private var pushRegistered = ""

    init { scope.launch { reload() } }

    fun eligible(): Boolean {
        if (settings.mock) return true
        val cm = context.getSystemService(ConnectivityManager::class.java)
        val caps = cm.getNetworkCapabilities(cm.activeNetwork) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            (!settings.wifiOnly || caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI))
    }
    private fun api(): BlogApi = if (settings.mock) mockApi else HttpApi(settings.origin,
        vault.get("monitorToken") ?: throw IOException("서버 페어링을 먼저 완료하세요."), httpClient)

    private fun reload() {
        val array = JSONArray(store.packages(settings.scope))
        mutable.update { it.copy(events = store.events(settings.scope), packages = List(array.length()) { i -> ContentPackage.parse(array.getJSONObject(i)) },
            lastSync = store.lastSync(settings.scope), mock = settings.mock, configured = settings.configured) }
    }
    private fun ingest(key: String, events: List<BlogEvent>) {
        if (key != settings.scope) return
        store.apply(key, events)
        events.filter { runCatching { Instant.parse(it.occurredAt).isAfter(Instant.now().minusSeconds(300)) }.getOrDefault(false) }.forEach {
            Notifications.show(context, store, key, it.id, eventLabel(it.type))
        }
        reload()
    }
    suspend fun sync() = withContext(Dispatchers.IO) {
        syncMutex.withLock {
            if (!eligible()) throw IOException("Wi-Fi 연결을 기다리는 중입니다.")
            val key = settings.scope
            val api = api()
            while (true) {
                val before = store.cursor(key)
                val events = api.events(before)
                if (events.isEmpty()) break
                require(events.all { it.sequence > before }) { "잘못된 서버 이벤트 커서" }
                ingest(key, events)
            }
            store.savePackages(key, api.packages())
            registerPush(api)
            reload()
            mutable.update { it.copy(connected = true, message = if (settings.mock) "Mock 동기화 완료 · 실제 게시 아님" else "서버 동기화 완료") }
        }
    }
    private fun registerPush(api: BlogApi) {
        if (api !is HttpApi) return
        runCatching {
            val token = vault.get("fcmToken") ?: return
            val key = settings.scope + token
            if (pushRegistered == key) return
            val enabled = api.registerPush(token)
            pushRegistered = key
            mutable.update { it.copy(pushStatus = if (enabled) "FCM 등록됨" else "FCM 토큰 등록됨 · 서버 발송 설정 필요") }
        }.onFailure { mutable.update { it.copy(pushStatus = "FCM 등록 재시도 대기") } }
    }
    fun saveFcmToken(token: String) {
        scope.launch { runCatching { vault.put("fcmToken", token); sync() }.onFailure { report(it) } }
    }
    fun report(error: Throwable) {
        if (error is CancellationException) return
        val message = when (error) {
            is ApiFailure -> error.message.orEmpty()
            is IllegalArgumentException -> error.message ?: "응답 검증 실패"
            else -> "연결 또는 저장 작업 실패. Wi-Fi와 서버 설정을 확인하세요."
        }
        mutable.update { it.copy(connected = false, message = message) }
    }
    fun message(value: String) { mutable.update { it.copy(message = value) } }
    fun start() { foreground = true; reconnect() }
    fun stop() { foreground = false; closeSocket(); reconnectJob?.cancel() }
    suspend fun shutdown() {
        stop(); scope.coroutineContext[Job]?.cancelAndJoin(); store.close()
        httpClient.connectionPool.evictAll(); httpClient.dispatcher.executorService.shutdown()
    }
    private fun closeSocket() { generation.incrementAndGet(); socket?.cancel(); socket = null }
    fun networkChanged() {
        if (!eligible()) {
            closeSocket()
            mutable.update { it.copy(connected = false, message = "Wi-Fi 연결 대기 · 저장된 이력 표시") }
        } else if (foreground) reconnect()
        BackgroundSync.enqueue(context)
    }
    fun reconnect() {
        reconnectJob?.cancel()
        closeSocket()
        reconnectJob = scope.launch {
            try { sync(); attempt = 0; if (foreground && !settings.mock) openSocket() }
            catch (e: CancellationException) { throw e }
            catch (e: Exception) { report(e); if (e !is ApiFailure || e.status != 401) scheduleRetry() }
        }
    }
    private fun scheduleRetry() {
        if (!foreground) return
        val delayMs = (1000L shl attempt.coerceAtMost(5)).coerceAtMost(30_000)
        attempt++
        reconnectJob = scope.launch { delay(delayMs); if (foreground) reconnect() }
    }
    private fun openSocket() {
        val http = api() as HttpApi
        val key = settings.scope
        val version = generation.get()
        socket = http.client.newWebSocket(http.request("/api/v1/events/ws?after=${store.cursor(key)}").build(), object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                if (version != generation.get() || key != settings.scope) return
                scope.launch {
                    try {
                        if (version != generation.get() || key != settings.scope) return@launch
                        val frame = JSONObject(text)
                        // A socket frame is a wake-up hint. The serialized HTTP cursor drain
                        // prevents concurrent callback ordering from skipping persisted events.
                        if (frame.optString("type") == "events") sync()
                        if (version == generation.get() && key == settings.scope) mutable.update { it.copy(connected = true) }
                    } catch (e: Exception) { report(e); webSocket.cancel() }
                }
            }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                if (version != generation.get()) return
                report(if (response?.code == 401 || response?.code == 403) ApiFailure(401) else t)
                if (response?.code !in listOf(401, 403)) scheduleRetry()
            }
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                if (version != generation.get()) return
                if (code == 4401) report(ApiFailure(401)) else scheduleRetry()
            }
            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) { webSocket.close(code, null) }
        })
    }

    private fun action(block: suspend () -> Unit) { scope.launch {
        actionMutex.withLock {
            mutable.update { it.copy(busy = true) }
            try { block() } catch (e: Exception) { report(e) }
            finally { mutable.update { it.copy(busy = false) } }
        }
    } }
    fun pair(origin: String, code: String, name: String) = action {
        val valid = validateOrigin(origin, BuildConfig.DEBUG)
        require(name.isNotBlank() && name.length <= 100)
        reconnectJob?.cancel()
        closeSocket()
        syncMutex.withLock {
            val result = HttpApi.pair(valid, code, name, httpClient)
            vault.put("monitorToken", result.getString("token"))
            settings.origin = valid; settings.deviceName = name; settings.deviceId = result.getString("device_id")
            settings.mock = false; settings.configured = true
            mutable.update { MonitorState(mock = false, configured = true, busy = true, message = "페어링 완료") }
            reload()
        }
        reconnect()
    }
    fun useMock() = action {
        reconnectJob?.cancel()
        closeSocket()
        syncMutex.withLock {
            settings.mock = true; settings.configured = true
            mutable.value = MonitorState(mock = true, configured = true, busy = true)
        }
        sync()
    }
    fun wifiOnly(value: Boolean) { settings.wifiOnly = value; networkChanged() }
    fun simulatePush() = action {
        require(settings.mock)
        val event = mockApi.simulate(store.cursor(settings.scope))
        Notifications.show(context, store, settings.scope, event.id, "Mock 알림: " + eventLabel(event.type))
        sync()
    }
    fun preview(item: ContentPackage) = action {
        require(!item.expired()) { "콘텐츠 만료" }
        val result = PreviewBuilder.build(api().download(item.id, "zip", 16 * 1024 * 1024), item)
        mutable.update { it.copy(preview = result, message = "이미지를 포함한 안전한 미리보기 준비 완료") }
    }
    fun completeManual(item: ContentPackage, postUrl: String) = action {
        require(!item.expired()) { "콘텐츠 만료" }
        val url = java.net.URI(postUrl.trim())
        require(url.scheme == "https" && url.host in setOf("blog.naver.com", "m.blog.naver.com") &&
            url.userInfo == null && url.port == -1 && url.fragment == null && !url.path.isNullOrBlank() && url.path != "/") {
            "직접 발행한 네이버 글의 HTTPS 주소를 입력하세요."
        }
        api().completeManual(item.id, postUrl.trim())
        sync()
        message("수동 발행 완료를 사용자 신고로 기록했습니다. 실제 게시 여부 자동 검증은 하지 않습니다.")
    }
    fun closePreview() { mutable.update { it.copy(preview = null) } }
    fun download(item: ContentPackage, kind: String) = action {
        require(!item.expired()) { "콘텐츠 만료" }
        val directory = File(context.filesDir, "downloads").apply { mkdirs() }
        val target = File(directory, "${java.util.UUID.fromString(item.id)}.$kind")
        val temporary = File.createTempFile("download-", ".part", directory)
        try {
            api().downloadTo(item.id, kind, temporary)
            if (kind == "zip") {
                val digest = java.security.MessageDigest.getInstance("SHA-256")
                temporary.inputStream().use { input ->
                    val buffer = ByteArray(65536)
                    while (true) { val count = input.read(buffer); if (count < 0) break; digest.update(buffer, 0, count) }
                }
                require(digest.digest().joinToString("") { "%02x".format(it) } == item.sha256) { "패키지 SHA-256 불일치" }
            }
            require(!item.expired()) { "콘텐츠 만료" }
            java.nio.file.Files.move(temporary.toPath(), target.toPath(), java.nio.file.StandardCopyOption.REPLACE_EXISTING)
        } finally { temporary.delete() }
        mutable.update { it.copy(download = target, message = "다운로드 완료 · 저장 위치 선택 또는 공유 가능") }
    }
}
