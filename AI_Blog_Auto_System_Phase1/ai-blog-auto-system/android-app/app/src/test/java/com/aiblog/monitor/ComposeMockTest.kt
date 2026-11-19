package com.aiblog.monitor

import android.app.Application
import android.content.Context
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.runBlocking
import org.junit.Rule
import org.junit.Test
import org.junit.After
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28], application = Application::class)
class ComposeMockTest {
    private var repository: MonitorRepository? = null
    @After fun closeRepository() { runBlocking { repository?.shutdown() } }
    @get:Rule val compose = createComposeRule()
    @Test fun setupDashboardHistoryAndDownloads() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val repo = MonitorRepository(context).also { repository = it }
        runBlocking { repo.sync() }
        compose.setContent { MonitorScreen(repo) }
        compose.onNodeWithText("서버 연결 마법사").assertIsDisplayed()
        compose.onNodeWithText("Mock 모드 시작").performClick()
        compose.onNodeWithText("운영 현황").assertIsDisplayed()
        compose.onNodeWithText("이벤트", useUnmergedTree = true).performClick()
        compose.onNodeWithText("콘텐츠 업로드 완료").assertIsDisplayed()
        compose.onNodeWithText("콘텐츠", useUnmergedTree = true).performClick()
        compose.onNodeWithText("HTML 미리보기 · 전체 복사").performScrollTo().assertIsDisplayed()
        compose.waitUntil(5000) { !repo.state.value.busy }
        compose.onNodeWithText("Word").performScrollTo().performClick()
        compose.waitUntil(10000) { repo.state.value.download != null }
        org.junit.Assert.assertEquals(listOf(80.toByte(), 75.toByte()), repo.state.value.download!!.readBytes().take(2))
        compose.waitUntil(5000) { !repo.state.value.busy }
        compose.onNodeWithText("HTML 미리보기 · 전체 복사").performScrollTo().performClick()
        compose.waitUntil(10000) { repo.state.value.preview != null }
        compose.onNodeWithText("글 전체 복사").performClick()
        val clipboard = context.getSystemService(android.content.ClipboardManager::class.java)
        org.junit.Assert.assertEquals(repo.state.value.preview!!.text, clipboard.primaryClip!!.getItemAt(0).text.toString())
        org.junit.Assert.assertEquals(repo.state.value.preview!!.html, clipboard.primaryClip!!.getItemAt(0).htmlText)
        compose.onNodeWithText("닫기").performClick()
        compose.waitUntil(5000) { repo.state.value.preview == null }
        compose.onNodeWithText("수동 발행 완료 기록").performScrollTo().performClick()
        compose.onNodeWithText("게시한 글 HTTPS 주소").performTextInput("https://blog.naver.com/mock/123")
        compose.onNodeWithText("직접 발행했음 · 기록").performClick()
        compose.waitUntil(10000) { repo.state.value.events.any { it.type == "MANUAL_PUBLISH_COMPLETED" } }
        compose.onNodeWithText("수동 발행 완료 (사용자 신고)").performScrollTo().assertIsDisplayed()
    }
}
