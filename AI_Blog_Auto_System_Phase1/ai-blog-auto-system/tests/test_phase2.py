import base64
import io
import json
import os
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "windows-app"))

import httpx
import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QWizard

from blog_gui.scheduling import ScheduleEngine, missed_schedule, triggers
from blog_gui.services import ServiceError, Services, safe_error
from blog_gui.storage import Settings, Store
from blog_gui.window import MainWindow, SetupWizard


class MemoryVault:
    def __init__(self):
        self.values = {}

    def get(self, name):
        return self.values.get(name, "")

    def set(self, name, value):
        self.values[name] = value


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "desktop")


def service_with_transport(store, handler):
    return Services(store, lambda: httpx.Client(transport=httpx.MockTransport(handler)))


def test_mock_article_dedup_and_png_without_key(store):
    service = Services(store)
    config = Settings(mock=False)
    article = service.write_article(config, "", "테스트 주제")
    again = service.write_article(config, "", "테스트 주제")
    assert article["mock"] and article["id"] == again["id"]
    assert len(store.articles()) == 1
    assert len(article["title_candidates"]) == 3
    result = service.generate_image(config, "", "도시 일러스트", "1536x1024")
    with Image.open(result["path"]) as image:
        assert image.size == (1536, 1024) and image.format == "PNG"
    assert result["mock"]
    assert Path(result["path"]).with_suffix(".json").exists()


def test_dedup_beyond_history_limit_and_after_restart(store):
    service = Services(store)
    original = service.write_article(Settings(), "", "original")
    for i in range(101):
        store.save_article({"id": str(i), "created_at": "2099", "signature": f"different-{i}"})
    reopened = Store(store.directory)
    again = Services(reopened).write_article(Settings(), "", "original")
    assert again["id"] == original["id"]


def test_mock_news_recollection_does_not_create_duplicate_article(store):
    service = Services(store)
    config = Settings()
    first = service.write_article(config, "", "topic", service.collect_news(config))
    second = service.write_article(config, "", "topic", service.collect_news(config))
    assert first["id"] == second["id"]


def test_live_rss_parsing_dedup_and_no_script_execution(store):
    rss = b'''<rss version="2.0"><channel><title>test</title>
    <item><title>News</title><link>https://example.com/story</link><description>&lt;b&gt;Summary&lt;/b&gt;</description></item>
    <item><title>News</title><link>https://example.com/story</link></item>
    <item><title>Bad</title><link>javascript:alert(1)</link></item></channel></rss>'''
    service = service_with_transport(store, lambda r: httpx.Response(200, content=rss))
    config = Settings(mock=False, rss_urls="https://example.com/rss")
    items = service.collect_news(config)
    assert len(items) == 1 and not items[0]["mock"]
    assert len(service.collect_news(config)) == 1 and len(store.news()) == 1


def test_rss_size_and_http_rejected(store):
    service = service_with_transport(store, lambda r: httpx.Response(200, content=b"x" * (2*1024*1024+1)))
    with pytest.raises(ServiceError):
        service.collect_news(Settings(mock=False, rss_urls="https://example.com/rss"))
    with pytest.raises(ServiceError):
        service.collect_news(Settings(mock=False, rss_urls="http://example.com/rss"))


def test_openai_text_and_image_contract(store):
    content = {"title_candidates": ["a", "b", "c"], "title": "title", "summary": "summary",
               "sections": [{"heading": "head", "body": "body"}], "tags": ["tag"], "seo_keywords": ["key"]}
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buffer, format="PNG")
    calls = []
    def handler(request):
        calls.append(request)
        body = json.loads(request.content)
        assert request.headers["Authorization"] == "Bearer test-api-key"
        if request.url.path.endswith("responses"):
            assert body["store"] is False and body["text"]["format"]["type"] == "json_object"
            return httpx.Response(200, json={"status": "completed", "output": [{"content": [{"type": "output_text", "text": json.dumps(content)}]}]})
        assert body["size"] == "1024x1024" and body["n"] == 1
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(buffer.getvalue()).decode()}]})
    service = service_with_transport(store, handler)
    config = Settings(mock=False)
    article = service.write_article(config, "test-api-key", "topic")
    result = service.generate_image(config, "test-api-key", "illustration")
    assert not article["mock"] and not result["mock"] and len(calls) == 2
    assert "test-api-key" not in store.path.read_bytes().decode(errors="ignore")


@pytest.mark.parametrize("body", [
    {"status": "incomplete", "output": []},
    {"status": "completed", "output": [{"content": [{"type": "output_text", "text": "not JSON"}]}]},
    {"status": "completed", "output": [{"content": [{"type": "output_text", "text": "{}"}]}]},
])
def test_invalid_ai_response_is_not_saved(store, body):
    service = service_with_transport(store, lambda r: httpx.Response(200, json=body))
    with pytest.raises(ServiceError):
        service.write_article(Settings(mock=False), "test-key", "topic")
    assert store.articles() == []


def test_secrets_not_in_errors_or_config(store):
    request = httpx.Request("POST", "https://api.openai.com/v1/responses", headers={"Authorization": "Bearer SECRET"})
    response = httpx.Response(401, request=request, text="SECRET")
    with pytest.raises(httpx.HTTPStatusError) as caught:
        response.raise_for_status()
    assert "SECRET" not in safe_error(caught.value)
    store.save_settings(Settings())
    assert "key" not in store.get("config") and "token" not in store.get("config")


def test_schedule_timezone_weekdays_resume_and_toggle():
    config = Settings(schedule_enabled=True, times=["08:00"], weekdays=[0])
    before = datetime(2026, 11, 15, 23, 0, tzinfo=timezone.utc)  # Monday 08:00 Seoul
    trigger = list(triggers(config))[0]
    assert trigger.get_next_fire_time(None, before).hour == 8
    assert str(trigger.timezone) == "Asia/Seoul"
    assert missed_schedule(config, (before - timedelta(minutes=1)).isoformat(), before)
    engine = ScheduleEngine(lambda: None)
    try:
        engine.apply(config)
        assert len(engine.next_runs()) == 1
        config.schedule_enabled = False
        engine.apply(config)
        assert engine.next_runs() == []
    finally:
        engine.stop()


def test_scheduler_actually_dispatches():
    from apscheduler.events import EVENT_JOB_SUBMITTED
    fired = threading.Event()
    submitted = threading.Event()
    engine = ScheduleEngine(fired.set)
    try:
        engine.scheduler.add_listener(lambda event: submitted.set(), EVENT_JOB_SUBMITTED)
        engine.scheduler.add_job(fired.set, "date", run_date=datetime.now(timezone.utc) + timedelta(milliseconds=100))
        engine.scheduler.resume()
        assert fired.wait(3)
        # Wait for the scheduler to remove its one-shot job before shutting down
        # its job store; the callback can run before that bookkeeping completes.
        assert submitted.wait(3)
    finally:
        engine.stop()


def test_missed_schedule_warning_is_delivered():
    from apscheduler.events import JobExecutionEvent, EVENT_JOB_MISSED
    messages = []
    engine = ScheduleEngine(lambda: None, messages.append)
    try:
        engine.on_event(JobExecutionEvent(EVENT_JOB_MISSED, "test", "default", datetime.now(timezone.utc)))
        assert "놓쳐" in messages[0]
    finally:
        engine.stop()


@pytest.mark.parametrize("changes", [dict(times=["25:00"]), dict(times=["08:00", "08:00"]), dict(weekdays=[]), dict(server_url="http://evil.com")])
def test_invalid_settings_rejected(changes):
    with pytest.raises(ValueError):
        Settings(**changes).validate()


@pytest.fixture
def window(qtbot, store):
    vault = MemoryVault()
    vault.set("server", "test-token")
    def handler(request):
        assert request.headers.get("X-Device-Token") == "test-token" or request.url.path.endswith("health")
        if request.method == "POST":
            event = json.loads(request.content)
            return httpx.Response(200, json={"event_id": event["event_id"], "accepted": True, "new": True})
        return httpx.Response(200, json={"status": "ok"} if request.url.path.endswith("health") else [])
    window = MainWindow(store, vault, service_with_transport(store, handler), browser=lambda url: True)
    qtbot.addWidget(window)
    window.show()
    yield window
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    window.close()


def click(qtbot, window, key, page=None):
    if page is not None:
        window.nav.setCurrentRow(page)
    window.buttons[key].click()
    qtbot.waitUntil(lambda: not window.busy, timeout=15000)


def test_gui_news_writer_image_exports_and_logs(qtbot, window, tmp_path, monkeypatch):
    click(qtbot, window, "collect_news", 4)
    assert window.news_table.rowCount() == 3
    click(qtbot, window, "open_source")
    click(qtbot, window, "use_news")
    click(qtbot, window, "write_article")
    assert window.article is None  # review gate
    window.review_source.setChecked(True)
    click(qtbot, window, "write_article")
    assert "MOCK" in window.article_view.toPlainText()
    click(qtbot, window, "copy_article")
    assert QApplication.clipboard().text() == window.article_view.toPlainText()
    article_path = tmp_path / "article.txt"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (str(article_path), ""))
    click(qtbot, window, "export_article")
    assert "MOCK" in article_path.read_text(encoding="utf-8")
    click(qtbot, window, "clear_source")
    assert window.source is None
    click(qtbot, window, "generate_image", 6)
    assert window.image_label.pixmap() and not window.image_label.pixmap().isNull()
    image_path = tmp_path / "export.png"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (str(image_path), ""))
    click(qtbot, window, "save_image")
    assert image_path.exists()
    click(qtbot, window, "refresh_logs", 8)
    assert "완료" in window.log_view.toPlainText()
    log_path = tmp_path / "logs.txt"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (str(log_path), ""))
    click(qtbot, window, "export_logs")
    assert log_path.stat().st_size > 0
    window.log_level.setCurrentText("ERROR")
    assert "[INFO]" not in window.log_view.toPlainText()
    click(qtbot, window, "clear_logs")
    assert window.store.logs() == []


def test_dashboard_local_check_does_not_change_real_settings(qtbot, window, monkeypatch):
    window.config.mock = False
    window.config.scheduled_image = False
    def no_network():
        raise AssertionError("Mock diagnostic must not contact server or AI")
    monkeypatch.setattr(window.services, "client_factory", no_network)
    click(qtbot, window, "check_local", 0)
    assert window.article["mock"] and len(window.article["images"]) == 1
    assert window.config.mock is False and window.config.scheduled_image is False
    state = window.store.get("last_authoring_run")
    assert state["status"] == "completed" and Path(state["path"]).is_file()
    assert "completed" in window.local_result.text()
    click(qtbot, window, "author_now")
    assert "API 키" in window.activity.text()
    assert window.store.get("last_authoring_run")["status"] == "failed"


def test_gui_server_settings_schedule_account(qtbot, window, monkeypatch):
    click(qtbot, window, "connect", 2)
    assert "ONLINE" in window.connection.text()
    click(qtbot, window, "send_event")
    assert "1건" in window.connection.text()
    click(qtbot, window, "flush")
    assert "0건" in window.connection.text()
    window.api_key.setText("test-api-key")
    window.server_token.setText("test-token")
    click(qtbot, window, "save_settings", 1)
    assert window.vault.get("openai") == "test-api-key" and not window.api_key.text()
    assert b"test-api-key" not in window.store.path.read_bytes()
    click(qtbot, window, "delete_key")
    assert not window.vault.get("openai")
    click(qtbot, window, "delete_token")
    assert not window.vault.get("server")
    click(qtbot, window, "connect", 2)
    assert "실패" in window.connection.text()
    window.schedule_times.setText("09:15, 17:45")
    window.schedule_images.setChecked(True)
    click(qtbot, window, "save_schedule", 3)
    assert window.config.times == ["09:15", "17:45"]
    click(qtbot, window, "toggle_schedule")
    assert window.config.schedule_enabled and len(window.engine.next_runs()) == 2
    click(qtbot, window, "run_schedule")
    assert window.article and window.image and window.store.get("last_schedule_run")
    click(qtbot, window, "toggle_schedule")
    assert not window.config.schedule_enabled
    opened = []
    window.browser = lambda url: opened.append(url.toString()) or True
    click(qtbot, window, "naver_login", 7)
    assert opened == ["https://nid.naver.com/nidlogin.login"]
    window.login_state.setCurrentText("성공")
    click(qtbot, window, "record_login")
    assert "사용자 신고" in window.login_label.text()
    click(qtbot, window, "reset_login")
    assert window.store.get("naver_status")["state"] == "확인 불가"
    monkeypatch.setattr(SetupWizard, "exec", lambda self: QWizard.DialogCode.Accepted)
    click(qtbot, window, "wizard", 1)
    click(qtbot, window, "refresh", 0)


def test_setup_wizard_completion_persists_no_plaintext_secrets(qtbot, store):
    vault = MemoryVault()
    wizard = SetupWizard(store, vault)
    qtbot.addWidget(wizard)
    wizard.show()
    qtbot.mouseClick(wizard.button(QWizard.WizardButton.NextButton), Qt.MouseButton.LeftButton)
    wizard.token.setText("server-secret")
    qtbot.mouseClick(wizard.button(QWizard.WizardButton.NextButton), Qt.MouseButton.LeftButton)
    wizard.key.setText("openai-secret")
    qtbot.mouseClick(wizard.button(QWizard.WizardButton.FinishButton), Qt.MouseButton.LeftButton)
    assert store.settings().initialized
    assert vault.get("openai") == "openai-secret"
    assert b"secret" not in store.path.read_bytes()


def test_gui_remains_responsive_and_prevents_close_during_task(qtbot, window):
    release = threading.Event()
    window.run_task("test", lambda: release.wait(3), lambda _: None)
    assert window.busy and not window.buttons["write_article"].isEnabled()
    window.nav.setCurrentRow(8)
    assert window.pages.currentIndex() == 8
    window.close()
    assert window.isVisible()
    release.set()
    qtbot.waitUntil(lambda: not window.busy)


def test_gui_screenshot(qtbot, window):
    window.nav.setCurrentRow(0)
    qtbot.wait(100)
    path = Path(__file__).resolve().parents[1] / ".pytest-tmp" / "gui-dashboard.png"
    assert window.grab().save(str(path))
