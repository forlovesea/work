package com.aiblog.monitor

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.webkit.WebView
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.content.FileProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.time.Instant

class MainActivity : ComponentActivity() {
    private val repository get() = (application as MonitorApp).repository
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MonitorScreen(repository) }
    }
    override fun onStart() { super.onStart(); repository.start() }
    override fun onStop() { repository.stop(); super.onStop() }
}

private val Navy = Color(0xFF19334A)
private val Teal = Color(0xFF087E74)

@Composable
fun MonitorScreen(repo: MonitorRepository) {
    val state by repo.state.collectAsStateWithLifecycle()
    var tab by rememberSaveable { mutableIntStateOf(if (repo.settings.configured) 0 else 3) }
    var now by remember { mutableStateOf(Instant.now()) }
    LaunchedEffect(Unit) { while (true) { now = Instant.now(); delay(1000) } }
    MaterialTheme(colorScheme = lightColorScheme(primary = Teal, secondary = Navy, background = Color(0xFFF3F6F9), surface = Color.White)) {
        Scaffold(modifier = Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.safeDrawing),
            bottomBar = {
                NavigationBar {
                    listOf("대시보드", "이벤트", "콘텐츠", "설정").forEachIndexed { i, title ->
                        NavigationBarItem(selected = tab == i, onClick = { tab = i },
                            icon = { Text(listOf("◉", "≡", "▣", "⚙")[i], fontSize = 22.sp) }, label = { Text(title) })
                    }
                }
            }) { padding ->
            Column(Modifier.padding(padding).fillMaxSize()) {
                Column(Modifier.fillMaxWidth().background(Navy).padding(20.dp)) {
                    Text("AI BLOG MONITOR", color = Color.White, fontSize = 23.sp, fontWeight = FontWeight.Bold)
                    Text(if (state.mock) "MOCK · 서버 없이 모든 기능 체험" else "${repo.settings.deviceName} · ${if (state.connected) "ONLINE" else "OFFLINE"}",
                        color = Color(0xFF9EDFD1), modifier = Modifier.padding(top = 6.dp))
                }
                if (state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                if (state.message.isNotEmpty()) Text(state.message, modifier = Modifier.fillMaxWidth().padding(12.dp), style = MaterialTheme.typography.bodySmall)
                when (tab) {
                    0 -> DashboardScreen(state, repo)
                    1 -> EventScreen(state)
                    2 -> PackageScreen(state, now, repo)
                    else -> SettingsScreen(state, repo) { tab = 0 }
                }
            }
        }
        state.preview?.let { preview -> PreviewDialog(preview, now, repo) }
    }
}

@Composable
private fun DashboardScreen(state: MonitorState, repo: MonitorRepository) {
    val summary = remember(state.events) { dashboard(state.events) }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("운영 현황", style = MaterialTheme.typography.headlineSmall)
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("서버  ${if (state.connected) "ONLINE" else "OFFLINE / 동기화 대기"}", fontWeight = FontWeight.Bold)
                Text("Windows  ${summary.windows}")
                Text("로그인  ${summary.login}")
                Text("발행 상태  ${summary.publication}")
                Text("마지막 동기화  ${state.lastSync.ifEmpty { "기록 없음" }}", style = MaterialTheme.typography.bodySmall)
            }
        }
        Text("오늘의 집계 · 최근 1,000개 기준 · 한국 시간", style = MaterialTheme.typography.titleMedium)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Metric("작성", summary.generated, Modifier.weight(1f)); Metric("실제 발행 성공", summary.published, Modifier.weight(1f))
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Metric("발행 실패", summary.failed, Modifier.weight(1f)); Metric("수동 발행 요청", summary.manual, Modifier.weight(1f))
        }
        Button(onClick = repo::reconnect, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("지금 동기화") }
        if (state.mock) OutlinedButton(onClick = repo::simulatePush, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Mock 알림 발생") }
        Text("Mock 성공은 실제 발행 건수에 포함하지 않습니다. 오프라인 상태에서는 저장된 마지막 상태를 표시합니다.", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable private fun Metric(label: String, count: Int, modifier: Modifier) {
    Card(modifier) { Column(Modifier.padding(16.dp)) { Text(label); Text("$count", fontSize = 30.sp, color = Teal, fontWeight = FontWeight.Bold) } }
}

@Composable private fun EventScreen(state: MonitorState) {
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { Text("이벤트 이력", style = MaterialTheme.typography.headlineSmall, modifier = Modifier.padding(vertical = 12.dp)) }
        if (state.events.isEmpty()) item { Text("동기화된 이벤트가 없습니다.") }
        items(state.events, key = { it.id }) { event ->
            Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(eventLabel(event.type), fontWeight = FontWeight.Bold)
                Text(event.occurredAt, style = MaterialTheme.typography.bodySmall)
                Text("#${event.sequence} · ${event.type}", style = MaterialTheme.typography.labelSmall)
            } }
        }
        item { Text("최근 1,000개 표시 · UUID 중복 제거 · 재연결 시 누락 구간 동기화", style = MaterialTheme.typography.bodySmall) }
    }
}

@Composable private fun PackageScreen(state: MonitorState, now: Instant, repo: MonitorRepository) {
    val context = LocalContext.current
    val coroutine = rememberCoroutineScope()
    var saveFile by remember { mutableStateOf<File?>(null) }
    var completing by remember { mutableStateOf<ContentPackage?>(null) }
    var postUrl by remember { mutableStateOf("") }
    completing?.let { item ->
        AlertDialog(onDismissRequest = { completing = null }, title = { Text("수동 발행 완료 기록") },
            text = { Column {
                Text("공식 편집기에서 직접 게시한 뒤 글 주소를 입력하세요. 이 버튼은 글을 게시하지 않으며 사용자 신고만 기록합니다.")
                OutlinedTextField(value = postUrl, onValueChange = { postUrl = it }, label = { Text("게시한 글 HTTPS 주소") })
            } },
            confirmButton = { TextButton(enabled = !item.expired(now) && postUrl.isNotBlank(), onClick = {
                repo.completeManual(item, postUrl); completing = null
            }) { Text("직접 발행했음 · 기록") } },
            dismissButton = { TextButton(onClick = { completing = null }) { Text("취소") } })
    }
    val save = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream")) { uri ->
        val file = saveFile
        if (uri != null && file != null) coroutine.launch {
            try {
                withContext(Dispatchers.IO) { context.contentResolver.openOutputStream(uri)?.use { out -> file.inputStream().use { it.copyTo(out) } } ?: error("저장 실패") }
                repo.message("선택한 위치에 저장했습니다.")
            } catch (e: Exception) { repo.report(e) }
        }
    }
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("수동 발행 콘텐츠", style = MaterialTheme.typography.headlineSmall, modifier = Modifier.padding(vertical = 12.dp)) }
        item { OutlinedButton(onClick = repo::reconnect, enabled = !state.busy) { Text("목록 새로고침") } }
        if (state.packages.isEmpty()) item { Text("저장된 콘텐츠가 없습니다.") }
        items(state.packages, key = { it.id }) { item ->
            val enabled = !item.expired(now) && !state.busy
            Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("콘텐츠 ${item.id.take(8)}", fontWeight = FontWeight.Bold)
                Text("업로드 ${item.uploadedAt}", style = MaterialTheme.typography.bodySmall)
                Text("만료 ${item.expiresAt}", style = MaterialTheme.typography.bodySmall)
                Text(item.remaining(now), color = if (item.expired(now)) MaterialTheme.colorScheme.error else Teal, fontWeight = FontWeight.Bold)
                Text("%.1f KiB".format(item.size / 1024.0))
                Button(onClick = { repo.preview(item) }, enabled = enabled, modifier = Modifier.fillMaxWidth()) { Text("HTML 미리보기 · 전체 복사") }
                val completed = state.events.any { it.type == "MANUAL_PUBLISH_COMPLETED" && org.json.JSONObject(it.payload).optString("package_id") == item.id }
                OutlinedButton(onClick = { completing = item; postUrl = "" }, enabled = enabled && !completed,
                    modifier = Modifier.fillMaxWidth()) { Text(if (completed) "수동 발행 완료 (사용자 신고)" else "수동 발행 완료 기록") }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { repo.download(item, "docx") }, enabled = enabled, modifier = Modifier.weight(1f), contentPadding = PaddingValues(8.dp)) { Text("Word") }
                    OutlinedButton(onClick = { repo.download(item, "zip") }, enabled = enabled, modifier = Modifier.weight(1f), contentPadding = PaddingValues(8.dp)) { Text("전체 ZIP") }
                    OutlinedButton(onClick = { repo.download(item, "html") }, enabled = enabled, modifier = Modifier.weight(1f), contentPadding = PaddingValues(8.dp)) { Text("HTML") }
                }
            } }
        }
        state.download?.let { file -> item {
            Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(16.dp)) {
                Text("다운로드 완료", fontWeight = FontWeight.Bold)
                Text(file.name, style = MaterialTheme.typography.bodySmall)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { saveFile = file; save.launch(file.name) }) { Text("저장 위치 선택") }
                    OutlinedButton(onClick = { share(context, file, repo) }) { Text("공유 / 열기") }
                }
            } }
        } }
        item { Text("다운로드된 파일은 기기에 남습니다. 이미지 포함 붙여넣기는 대상 앱에 따라 다르므로 ZIP/Word도 함께 사용하세요.", style = MaterialTheme.typography.bodySmall) }
    }
}

private fun share(context: Context, file: File, repo: MonitorRepository) {
    runCatching {
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", file)
        val mime = when (file.extension) { "docx" -> "application/vnd.openxmlformats-officedocument.wordprocessingml.document"; "zip" -> "application/zip"; else -> "text/html" }
        val intent = Intent(Intent.ACTION_SEND).setType(mime).putExtra(Intent.EXTRA_STREAM, uri)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION).apply { clipData = ClipData.newRawUri("콘텐츠", uri) }
        context.startActivity(Intent.createChooser(intent, "콘텐츠 공유"))
    }.onFailure { repo.message("파일을 열 수 있는 앱이 없습니다. 저장 위치 선택을 사용하세요.") }
}

@Composable private fun SettingsScreen(state: MonitorState, repo: MonitorRepository, done: () -> Unit) {
    var origin by rememberSaveable { mutableStateOf(repo.settings.origin) }
    var name by rememberSaveable { mutableStateOf(repo.settings.deviceName) }
    var code by remember { mutableStateOf("") }
    var wifiOnly by remember { mutableStateOf(repo.settings.wifiOnly) }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted -> repo.message(if (granted) "알림 권한 허용됨" else "알림 권한이 없어도 앱 내 이력을 확인할 수 있습니다.") }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("서버 연결 마법사", style = MaterialTheme.typography.headlineSmall)
        Text("먼저 Mock 모드로 체험하거나, 관리자가 발급한 10분 유효 페어링 코드를 입력하세요.")
        Button(onClick = { repo.useMock(); done() }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Mock 모드 시작") }
        HorizontalDivider()
        OutlinedTextField(value = origin, onValueChange = { origin = it }, label = { Text("서버 주소") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text("기기 이름") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(value = code, onValueChange = { code = it }, label = { Text("페어링 코드") }, visualTransformation = PasswordVisualTransformation(), singleLine = true, modifier = Modifier.fillMaxWidth())
        Button(onClick = { repo.pair(origin, code, name); code = "" }, enabled = !state.busy && code.isNotBlank(), modifier = Modifier.fillMaxWidth()) { Text("서버 페어링") }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("Wi-Fi에서만 서버 연결", modifier = Modifier.padding(top = 12.dp))
            Switch(checked = wifiOnly, onCheckedChange = { wifiOnly = it; repo.wifiOnly(it) })
        }
        OutlinedButton(onClick = {
            if (android.os.Build.VERSION.SDK_INT >= 33) permission.launch(Manifest.permission.POST_NOTIFICATIONS)
            else repo.message("시스템 설정에서 앱 알림 권한을 확인하세요.")
        }, modifier = Modifier.fillMaxWidth()) { Text("알림 권한 설정") }
        Text(state.pushStatus, style = MaterialTheme.typography.bodySmall)
        Text("화면을 보고 있을 때 WebSocket으로 갱신합니다. 백그라운드에서는 FCM과 WorkManager를 사용하며, 절전 모드에서는 수신이 지연될 수 있습니다.", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable private fun PreviewDialog(preview: Preview, now: Instant, repo: MonitorRepository) {
    val context = LocalContext.current
    val expired = !now.isBefore(Instant.parse(preview.expiresAt))
    Dialog(onDismissRequest = repo::closePreview, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.safeDrawing)) {
            Column {
                Row(Modifier.fillMaxWidth().padding(12.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                    TextButton(onClick = repo::closePreview) { Text("닫기") }
                    Button(enabled = !expired, onClick = {
                        if (Instant.now().isBefore(Instant.parse(preview.expiresAt))) {
                            runCatching {
                                val content = clipboardContent(preview)
                                context.getSystemService(ClipboardManager::class.java).setPrimaryClip(content.clip)
                                repo.message(content.message)
                            }.onFailure { repo.message("복사 실패 또는 용량 초과 · Word/ZIP 파일을 사용하세요.") }
                        }
                    }) { Text("글 전체 복사") }
                }
                if (expired) Text("콘텐츠가 만료되었습니다.", Modifier.padding(24.dp))
                else AndroidView(modifier = Modifier.fillMaxWidth().weight(1f), factory = { ctx ->
                    WebView(ctx).apply {
                        settings.javaScriptEnabled = false
                        settings.allowFileAccess = false
                        settings.allowContentAccess = false
                        settings.domStorageEnabled = false
                        settings.blockNetworkLoads = true
                        webViewClient = SafePreviewClient()
                        loadDataWithBaseURL("https://preview.invalid/", preview.html, "text/html", "UTF-8", null)
                    }
                }, onRelease = { it.stopLoading(); it.destroy() })
            }
        }
    }
}
