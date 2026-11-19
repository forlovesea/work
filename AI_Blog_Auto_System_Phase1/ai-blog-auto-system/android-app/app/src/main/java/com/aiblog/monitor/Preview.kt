package com.aiblog.monitor

import org.json.JSONObject
import org.jsoup.Jsoup
import org.jsoup.safety.Safelist
import java.io.ByteArrayOutputStream
import java.util.Base64
import java.util.zip.ZipInputStream

data class Preview(val packageId: String, val title: String, val html: String, val text: String, val expiresAt: String)

class SafePreviewClient : android.webkit.WebViewClient() {
    override fun shouldOverrideUrlLoading(view: android.webkit.WebView?, request: android.webkit.WebResourceRequest?) = true
    override fun shouldInterceptRequest(view: android.webkit.WebView?, request: android.webkit.WebResourceRequest?): android.webkit.WebResourceResponse? {
        // Android also intercepts data: URLs. Permit only our validated inline PNGs.
        if (request?.url?.toString()?.startsWith("data:image/png;base64,") == true) return null
        return android.webkit.WebResourceResponse("text/plain", "utf-8", byteArrayOf().inputStream())
    }
}

data class ClipboardContent(val clip: android.content.ClipData, val message: String)

fun clipboardContent(preview: Preview): ClipboardContent {
    require(java.time.Instant.now().isBefore(java.time.Instant.parse(preview.expiresAt))) { "콘텐츠 만료" }
    // Binder has a transaction size limit. Never truncate an article or crash on large inline images.
    val limit = 256 * 1024
    val textBytes = preview.text.toByteArray().size
    require(textBytes <= limit) { "클립보드 용량 초과 · Word/ZIP 파일을 사용하세요." }
    var html = preview.html
    var message = "전체 글을 HTML과 일반 텍스트로 복사했습니다."
    if (textBytes + html.toByteArray().size > limit) {
        val document = Jsoup.parse(html)
        document.select("img").remove()
        html = document.body().html()
        message = "전체 글 복사 완료 · 큰 이미지는 제외했습니다. 이미지는 ZIP을 사용하세요."
    }
    val clip = if (textBytes + html.toByteArray().size <= limit) android.content.ClipData.newHtmlText(preview.title.take(100), preview.text, html)
        else android.content.ClipData.newPlainText(preview.title.take(100), preview.text).also { message = "전체 글을 일반 텍스트로 복사했습니다. 서식과 이미지는 Word/ZIP을 사용하세요." }
    return ClipboardContent(clip, message)
}

object PreviewBuilder {
    fun build(data: ByteArray, item: ContentPackage): Preview {
        require(data.size <= 16 * 1024 * 1024) { "미리보기 용량 초과 · ZIP 다운로드를 이용하세요." }
        require(!item.expired()) { "콘텐츠 만료" }
        require(sha256(data) == item.sha256) { "패키지 무결성 검증 실패" }
        val files = linkedMapOf<String, ByteArray>()
        var total = 0L
        ZipInputStream(data.inputStream()).use { zip ->
            while (true) {
                val entry = zip.nextEntry ?: break
                val name = entry.name
                require(name in setOf("index.html", "article.txt", "article.docx", "manifest.json") || Regex("images/(thumbnail|body_[0-9]{2})\\.png").matches(name)) { "허용하지 않은 ZIP 경로" }
                require(name !in files && files.size < 34 && !entry.isDirectory)
                val output = ByteArrayOutputStream()
                val buffer = ByteArray(65536)
                while (true) {
                    val count = zip.read(buffer)
                    if (count < 0) break
                    total += count
                    require(total <= 24L * 1024 * 1024) { "미리보기 확장 크기 초과 · ZIP 다운로드를 이용하세요." }
                    output.write(buffer, 0, count)
                }
                files[name] = output.toByteArray()
            }
        }
        require(files.keys.containsAll(setOf("index.html", "article.txt", "article.docx", "manifest.json")))
        require(files.getValue("manifest.json").size <= 256 * 1024)
        require(files.getValue("index.html").size <= 2 * 1024 * 1024 && files.getValue("article.txt").size <= 2 * 1024 * 1024)
        val manifest = JSONObject(files.getValue("manifest.json").toString(Charsets.UTF_8))
        require(manifest.getString("content_id") == item.id && manifest.getString("format_version") == "1.0")
        val entries = manifest.getJSONArray("files")
        val declared = mutableSetOf<String>()
        for (i in 0 until entries.length()) {
            val entry = entries.getJSONObject(i)
            val name = entry.getString("path")
            require(declared.add(name))
            val bytes = files.getValue(name)
            require(bytes.size.toLong() == entry.getLong("size") && sha256(bytes) == entry.getString("sha256"))
        }
        require(declared == files.keys - "manifest.json")
        val imageOrder = manifest.getJSONArray("image_order")
        val images = (0 until imageOrder.length()).map { imageOrder.getString(it) }
        require(images.size == images.toSet().size && images.toSet() == files.keys.filter { it.startsWith("images/") }.toSet())
        val document = Jsoup.parse(files.getValue("index.html").toString(Charsets.UTF_8))
        document.select("img").forEach { image ->
            val path = image.attr("src")
            if (path !in images) image.remove() else image.attr("src", "data:image/png;base64," + Base64.getEncoder().encodeToString(files.getValue(path)))
        }
        val safe = Safelist.relaxed().removeTags("a").removeProtocols("img", "src", "http", "https").addProtocols("img", "src", "data")
        val clean = Jsoup.clean(document.body().html(), safe)
        val html = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'"><style>body{font-family:sans-serif;padding:16px;line-height:1.7;color:#172637}img{max-width:100%;height:auto}</style></head><body>$clean</body></html>"""
        require(!item.expired()) { "콘텐츠 만료" }
        return Preview(item.id, manifest.optString("title", "콘텐츠"), html, files.getValue("article.txt").toString(Charsets.UTF_8), item.expiresAt)
    }
}
