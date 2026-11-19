package com.aiblog.monitor

import android.content.Context
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.io.File
import java.security.MessageDigest
import java.time.Instant
import java.util.UUID
import java.util.concurrent.TimeUnit
import java.util.zip.ZipInputStream

fun sha256(data: ByteArray) = MessageDigest.getInstance("SHA-256").digest(data).joinToString("") { "%02x".format(it) }
class ApiFailure(val status: Int) : IOException(when(status) {
    401 -> "인증이 만료되거나 폐기되었습니다. 다시 페어링하세요."
    410 -> "콘텐츠가 만료되었습니다."
    503 -> "서버 파일을 사용할 수 없습니다."
    else -> "서버 요청 실패 (HTTP $status)"
})

interface BlogApi {
    fun completeManual(id: String, postUrl: String) { error("수동 완료 기록을 지원하지 않습니다.") }
    fun events(after: Long): List<BlogEvent>
    fun packages(): String
    fun download(id: String, kind: String, maxBytes: Int = 100 * 1024 * 1024): ByteArray
    fun downloadTo(id: String, kind: String, file: File) {
        val bytes = download(id, kind)
        file.outputStream().use { it.write(bytes); it.fd.sync() }
    }
}

class HttpApi(val origin: String, private val token: String, val client: OkHttpClient = httpClient()) : BlogApi {
    override fun completeManual(id: String, postUrl: String) {
        val safeId = UUID.fromString(id).toString()
        val body = JSONObject().put("confirmed", true).put("post_url", postUrl)
        json(request("/api/v1/packages/$safeId/manual-completion").post(body.toString().toRequestBody(JSON)).build())
    }
    fun request(path: String) = Request.Builder().url(origin + path).header("X-Device-Token", token)
    fun json(request: Request): String = client.newCall(request).execute().use { response ->
        if (!response.isSuccessful) throw ApiFailure(response.code)
        bounded(response, 4 * 1024 * 1024).toString(Charsets.UTF_8)
    }
    override fun events(after: Long): List<BlogEvent> {
        val rows = JSONArray(json(request("/api/v1/events?after=$after&limit=100").build()))
        return List(rows.length()) { BlogEvent.parse(rows.getJSONObject(it)) }
    }
    override fun packages() = json(request("/api/v1/packages").build())
    override fun download(id: String, kind: String, maxBytes: Int): ByteArray {
        val safeId = UUID.fromString(id).toString()
        require(kind in setOf("zip", "docx", "html", "txt"))
        return client.newCall(request("/api/v1/packages/$safeId/download?kind=$kind").build()).execute().use { response ->
            if (!response.isSuccessful) throw ApiFailure(response.code)
            val bytes = bounded(response, maxBytes)
            require(response.header("X-Content-SHA256") == sha256(bytes)) { "다운로드 SHA-256 검증 실패" }
            bytes
        }
    }
    override fun downloadTo(id: String, kind: String, file: File) {
        val safeId = UUID.fromString(id).toString()
        require(kind in setOf("zip", "docx", "html", "txt"))
        client.newCall(request("/api/v1/packages/$safeId/download?kind=$kind").build()).execute().use { response ->
            if (!response.isSuccessful) throw ApiFailure(response.code)
            val body = response.body ?: throw IOException("응답 본문 없음")
            require(body.contentLength() <= 100L * 1024 * 1024)
            val digest = MessageDigest.getInstance("SHA-256")
            var total = 0L
            file.outputStream().use { out ->
                body.byteStream().use { input ->
                    val buffer = ByteArray(65536)
                    while (true) {
                        val count = input.read(buffer)
                        if (count < 0) break
                        total += count
                        require(total <= 100L * 1024 * 1024) { "다운로드 용량 초과" }
                        digest.update(buffer, 0, count); out.write(buffer, 0, count)
                    }
                }
                out.fd.sync()
            }
            require(digest.digest().joinToString("") { "%02x".format(it) } == response.header("X-Content-SHA256")) { "다운로드 SHA-256 검증 실패" }
        }
    }
    fun registerPush(value: String): Boolean {
        val result = JSONObject(json(request("/api/v1/devices/me/push").put(JSONObject().put("token", value).toString().toRequestBody(JSON)).build()))
        return result.optBoolean("delivery_enabled")
    }
    companion object {
        val JSON = "application/json; charset=utf-8".toMediaType()
        fun httpClient() = OkHttpClient.Builder().followRedirects(false).followSslRedirects(false)
            .connectTimeout(15, TimeUnit.SECONDS).readTimeout(45, TimeUnit.SECONDS).callTimeout(120, TimeUnit.SECONDS).build()
        fun pair(origin: String, code: String, name: String, client: OkHttpClient = httpClient()): JSONObject {
            val data = JSONObject().put("code", code.trim()).put("device_name", name.trim())
            return JSONObject(HttpApi(origin, "", client).json(Request.Builder().url(origin + "/api/v1/pairing/claim")
                .post(data.toString().toRequestBody(JSON)).build()))
        }
        fun bounded(response: Response, limit: Int): ByteArray {
            val body = response.body ?: throw IOException("응답 본문 없음")
            require(body.contentLength() <= limit) { "파일 용량 초과" }
            val output = ByteArrayOutputStream()
            body.byteStream().use { input ->
                val buffer = ByteArray(65536)
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    require(output.size().toLong() + count <= limit) { "파일 용량 초과" }
                    output.write(buffer, 0, count)
                }
            }
            return output.toByteArray()
        }
    }
}

class MockApi(context: Context, private val created: Instant) : BlogApi {
    @Synchronized override fun completeManual(id: String, postUrl: String) {
        require(id == this.id)
        if (!Instant.now().isBefore(created.plusSeconds(48 * 3600))) throw ApiFailure(410)
        val payload = JSONObject().put("package_id", id).put("post_url", postUrl).put("verified", false).put("mock", true).toString()
        val existing = rows.firstOrNull { it.type == "MANUAL_PUBLISH_COMPLETED" }
        if (existing != null) { require(existing.payload == payload); return }
        rows.add(BlogEvent(rows.last().sequence + 1, UUID.randomUUID().toString(), "MANUAL_PUBLISH_COMPLETED", Instant.now().toString(), payload))
    }
    private val zip = context.assets.open("mock-package.zip").use { it.readBytes() }
    val id = "99f7d610-d944-4011-a8da-9dcdd88f1120"
    private val rows = mutableListOf<BlogEvent>().apply {
        listOf("PC_ONLINE", "NAVER_LOGIN_SUCCESS", "MOCK_PUBLISH_SUCCESS", "PACKAGE_UPLOAD_SUCCESS").forEachIndexed { i, type ->
            add(BlogEvent(i + 1L, UUID.nameUUIDFromBytes(type.toByteArray()).toString(), type, created.toString(), JSONObject().put("package_id", id).toString()))
        }
    }
    @Synchronized fun simulate(after: Long, type: String = "MANUAL_PUBLISH_REQUIRED"): BlogEvent {
        val event = BlogEvent(maxOf(after, rows.last().sequence) + 1, UUID.randomUUID().toString(), type, Instant.now().toString())
        rows.add(event)
        return event
    }
    @Synchronized override fun events(after: Long) = rows.filter { it.sequence > after }.take(100)
    override fun packages() = JSONArray().put(JSONObject().put("package_id", id).put("size", zip.size).put("sha256", sha256(zip))
        .put("uploaded_at", created.toString()).put("expires_at", created.plusSeconds(48 * 3600).toString()).put("deleted_at", JSONObject.NULL)).toString()
    override fun download(id: String, kind: String, maxBytes: Int): ByteArray {
        require(id == this.id)
        if (!Instant.now().isBefore(created.plusSeconds(48 * 3600))) throw ApiFailure(410)
        require(zip.size <= maxBytes) { "미리보기 용량 초과 · ZIP 다운로드를 이용하세요." }
        if (kind == "zip") return zip
        val name = mapOf("html" to "index.html", "txt" to "article.txt", "docx" to "article.docx").getValue(kind)
        ZipInputStream(zip.inputStream()).use { input ->
            while (true) {
                val entry = input.nextEntry ?: break
                if (entry.name == name) return input.readBytes()
            }
        }
        error("Mock 파일 없음")
    }
}
