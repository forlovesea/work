package com.aiblog.monitor

import org.json.JSONObject
import java.net.URI
import java.time.Duration
import java.time.Instant
import java.util.UUID

data class BlogEvent(val sequence: Long, val id: String, val type: String, val occurredAt: String, val payload: String = "{}") {
    fun json() = JSONObject().put("sequence", sequence).put("event_id", id).put("event_type", type)
        .put("occurred_at", occurredAt).put("payload", JSONObject(payload)).toString()
    companion object {
        fun parse(json: JSONObject) = BlogEvent(json.getLong("sequence"), json.getString("event_id"),
            json.getString("event_type"), json.getString("occurred_at"), json.optJSONObject("payload")?.toString() ?: "{}")
    }
}

data class ContentPackage(val id: String, val size: Long, val sha256: String, val uploadedAt: String,
                          val expiresAt: String, val deleted: Boolean = false) {
    fun expired(now: Instant = Instant.now()) = deleted || !now.isBefore(Instant.parse(expiresAt))
    fun remaining(now: Instant = Instant.now()): String {
        if (expired(now)) return "만료됨 · 다운로드 불가"
        val seconds = Duration.between(now, Instant.parse(expiresAt)).seconds.coerceAtLeast(0)
        return "남은 시간 %02d:%02d:%02d".format(seconds / 3600, seconds / 60 % 60, seconds % 60)
    }
    companion object {
        fun parse(json: JSONObject): ContentPackage {
            val id = UUID.fromString(json.getString("package_id")).toString()
            return ContentPackage(id, json.getLong("size"), json.getString("sha256"), json.getString("uploaded_at"),
                json.getString("expires_at"), !json.isNull("deleted_at"))
        }
    }
}

data class Dashboard(val windows: String = "확인 전", val login: String = "확인 전", val publication: String = "확인 전",
                     val generated: Int = 0, val published: Int = 0, val failed: Int = 0, val manual: Int = 0)

fun dashboard(events: List<BlogEvent>, now: Instant = Instant.now()): Dashboard {
    val sorted = events.sortedBy { it.sequence }
    val today = now.atZone(java.time.ZoneId.of("Asia/Seoul")).toLocalDate()
    val daily = sorted.filter { runCatching { Instant.parse(it.occurredAt).atZone(java.time.ZoneId.of("Asia/Seoul")).toLocalDate() == today }.getOrDefault(false) }
    return Dashboard(
        sorted.lastOrNull { it.type in setOf("PC_ONLINE", "PC_OFFLINE") }?.let { if (it.type == "PC_ONLINE") "ONLINE" else "OFFLINE" } ?: "확인 전",
        sorted.lastOrNull { it.type.startsWith("NAVER_LOGIN_") }?.let { eventLabel(it.type) } ?: "확인 전",
        sorted.lastOrNull { it.type.startsWith("PUBLISH_") || it.type.startsWith("MANUAL_PUBLISH_") || it.type == "MOCK_PUBLISH_SUCCESS" }?.let { eventLabel(it.type) } ?: "확인 전",
        daily.count { it.type == "CONTENT_GENERATED" }, daily.count { it.type == "PUBLISH_SUCCESS" },
        daily.count { it.type == "PUBLISH_FAILED" }, daily.count { it.type == "MANUAL_PUBLISH_REQUIRED" })
}

fun eventLabel(type: String): String = when (type) {
    "PC_ONLINE" -> "Windows 연결됨"; "PC_OFFLINE" -> "Windows 연결 끊김"
    "NAVER_LOGIN_SUCCESS" -> "네이버 로그인 확인"; "NAVER_LOGIN_FAILED" -> "네이버 로그인 실패"
    "NAVER_LOGIN_EXPIRED" -> "네이버 로그인 만료"; "CONTENT_GENERATED" -> "콘텐츠 작성 완료"
    "PUBLISH_STARTED" -> "발행 진행 중"; "PUBLISH_SUCCESS" -> "발행 성공"
    "PUBLISH_FAILED" -> "발행 실패"; "PUBLISH_UNCONFIRMED" -> "발행 확인 필요"
    "MOCK_PUBLISH_SUCCESS" -> "Mock 발행 성공 (실제 게시 아님)"
    "MANUAL_PUBLISH_REQUIRED" -> "수동 발행 필요"; "PACKAGE_UPLOAD_SUCCESS" -> "콘텐츠 업로드 완료"
    "MANUAL_PUBLISH_COMPLETED" -> "수동 발행 완료 (사용자 신고)"
    "PACKAGE_EXPIRING_6H" -> "콘텐츠 만료 6시간 이내"; "PACKAGE_EXPIRING_1H" -> "콘텐츠 만료 1시간 이내"
    "PACKAGE_DELETED" -> "만료 콘텐츠 삭제됨"; "SERVER_ERROR" -> "서버 오류"
    else -> type
}

fun validateOrigin(value: String, debug: Boolean): String {
    val uri = URI(value.trim())
    require(uri.host != null && uri.rawUserInfo == null && uri.rawQuery == null && uri.rawFragment == null &&
        uri.rawPath.orEmpty() in listOf("", "/") && uri.port in -1..65535) { "서버 주소는 경로 없는 HTTPS 주소여야 합니다." }
    require(uri.scheme == "https" || (debug && uri.scheme == "http" && uri.host in setOf("10.0.2.2", "127.0.0.1", "localhost"))) {
        "HTTPS가 필요합니다. 디버그 빌드의 로컬 테스트 주소만 HTTP를 허용합니다."
    }
    return value.trim().trimEnd('/')
}
