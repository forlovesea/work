import copy
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QMainWindow, QPlainTextEdit, QPushButton,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QWizard, QWizardPage, QHeaderView, QAbstractItemView, QScrollArea,
)

from .scheduling import ScheduleEngine, missed_schedule
from .services import Services, article_text, safe_error
from .storage import utcnow
from .exports import Publication, atomic_write, import_image, MAX_IMAGES
from .clipboard import copy_publication
from .preview import HtmlPreview
from .workflow import VERSION, author_locally
from .diagnostics import settings_report


def configure_font():
    """Load Hangul explicitly, including with Qt's offscreen test platform."""
    app = QApplication.instance()
    if app.property("blogFontLoaded"):
        return
    font_path = Path(os.getenv("WINDIR", "C:/Windows")) / "Fonts" / "malgun.ttf"
    if font_path.exists():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], 10))
    emoji_path = font_path.parent / "seguiemj.ttf"
    if emoji_path.exists():
        QFontDatabase.addApplicationFont(str(emoji_path))
    app.setProperty("blogFontLoaded", True)


class TaskSignals(QObject):
    progress = Signal(str)
    done = Signal(object)
    failed = Signal(str)


class Task(QRunnable):
    def __init__(self, operation):
        super().__init__()
        self.operation = operation
        self.signals = TaskSignals()

    def run(self):
        try:
            result = self.operation()
        except Exception as exc:
            self.signals.failed.emit(safe_error(exc))
        else:
            self.signals.done.emit(result)


def password_field(placeholder="변경할 때만 입력"):
    field = QLineEdit()
    field.setEchoMode(QLineEdit.EchoMode.Password)
    field.setPlaceholderText(placeholder)
    return field


class SetupWizard(QWizard):
    def __init__(self, store, vault, parent=None):
        super().__init__(parent)
        configure_font()
        self.store, self.vault = store, vault
        self.setWindowTitle("AI Blog Auto System · 최초 설정")
        self.resize(620, 460)
        config = store.settings()
        page = QWizardPage()
        page.setTitle("로컬 작업 공간을 준비합니다")
        layout = QVBoxLayout(page)
        info = QLabel("뉴스와 AI 초안을 만들고 예약 작업을 관리합니다.\nChatGPT Plus 사용자는 마법사 완료 후 설정에서 ChatGPT로 로그인하세요.\n예약 작업은 초안 생성이며 네이버 자동 발행은 실행하지 않습니다.")
        info.setWordWrap(True)
        layout.addWidget(info)
        self.addPage(page)
        page = QWizardPage()
        page.setTitle("서버 연결 · 나중에 설정 가능")
        form = QFormLayout(page)
        self.server = QLineEdit(config.server_url)
        form.addRow(QLabel("AI Blog 전용 HTTPS: https://61.105.141.21:8001\n같은 PC: http://127.0.0.1:8000\nChatGPT 글쓰기에는 서버 연결이 필요 없습니다."))
        self.device = QLineEdit(config.device_id)
        self.token = password_field("서버와 동일한 개발 토큰 (선택)")
        form.addRow("서버 주소", self.server)
        form.addRow("기기 ID", self.device)
        form.addRow("서버 토큰", self.token)
        self.addPage(page)
        page = QWizardPage()
        page.setTitle("AI 설정")
        form = QFormLayout(page)
        self.key = password_field("OpenAI API 키 (선택)")
        self.mock = QCheckBox("Mock 모드 — 외부 AI 호출 없음")
        self.mock.setChecked(config.mock)
        form.addRow("OpenAI API 키", self.key)
        form.addRow(self.mock)
        form.addRow(QLabel("ChatGPT 구독 사용자는 API 키를 비워 두세요.\n완료 후 설정 → Continue with ChatGPT → 모델 선택 → Mock 해제 → 설정 저장.\nAPI 방식을 별도로 선택한 경우만 API 요금이 발생합니다. 예약 기본값 OFF."))
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color:#b33d31")
        form.addRow(self.error)
        self.addPage(page)

    def accept(self):
        try:
            config = self.store.settings()
            config.server_url, config.device_id = self.server.text().strip(), self.device.text().strip()
            config.mock = self.mock.isChecked()
            config.initialized = True
            config.validate()
            if self.key.text().strip():
                self.vault.set("openai", self.key.text().strip())
            if self.token.text().strip():
                self.vault.set("server", self.token.text().strip())
            self.store.save_settings(config)
        except Exception as exc:
            self.error.setText(str(exc) if isinstance(exc, ValueError) else safe_error(exc))
            return
        super().accept()


class MainWindow(QMainWindow):
    scheduled = Signal()
    schedule_warning = Signal(str)

    def __init__(self, store, vault, services=None, browser=None):
        super().__init__()
        configure_font()
        self.store, self.vault = store, vault
        self.services = services or Services(store)
        self.services.chatgpt.vault = vault
        self.browser = browser or QDesktopServices.openUrl
        self.config = store.settings()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.active_task = None
        self.busy = False
        self.buttons = {}
        self.article = None
        self.image = None
        self.news_items = []
        self.setWindowTitle(f"AI Blog Auto System · v{VERSION}")
        self.resize(1180, 820)
        self.setMinimumSize(920, 680)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        self.nav = QListWidget()
        self.nav.setFixedWidth(180)
        self.pages = QStackedWidget()
        layout.addWidget(self.nav)
        layout.addWidget(self.pages, 1)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.build_dashboard()
        self.build_settings()
        self.build_server()
        self.build_schedule()
        self.build_news()
        self.build_writer()
        self.build_images()
        self.build_account()
        self.build_logs()
        self.build_output()
        self.nav.setCurrentRow(0)
        self.setStyleSheet("""
            QMainWindow { background: #f4f7fb; }
            QLabel { color: #17283f; }
            QListWidget { background: #17283f; color: white; border: 0; padding: 8px; font-size: 14px; }
            QListWidget::item { padding: 13px 5px; }
            QListWidget::item:selected { background: #287a83; border-radius: 4px; }
            QPushButton { padding: 8px 13px; background: #247982; color: white; border: 0; border-radius: 4px; }
            QPushButton:disabled { background: #99afb4; }
            QLineEdit, QPlainTextEdit, QComboBox { padding: 6px; background: white; color: #17283f; border: 1px solid #c9d4df; }
            QTableWidget { background: white; color: #17283f; gridline-color: #e3e9ef; }
        """)
        self.scheduled.connect(self.run_scheduled)
        self.schedule_warning.connect(lambda message: self.notify(message, "WARNING"))
        self.engine = ScheduleEngine(self.scheduled.emit, self.schedule_warning.emit)
        self.engine.apply(self.config)
        previous = self.store.get("last_seen")
        if missed_schedule(self.config, previous, datetime.now(timezone.utc)):
            self.store.log("WARNING", "앱 종료/PC OFF 동안 실행되지 않은 예약이 있습니다.")
            if self.config.resume_policy == "once":
                QTimer.singleShot(0, self.run_scheduled)
            else:
                self.store.log("INFO", "재개 정책에 따라 누락된 예약을 건너뛰었습니다.")
        self.heartbeat = QTimer(self)
        self.heartbeat.timeout.connect(self.tick)
        self.heartbeat.start(30000)
        self.store.log("INFO", "GUI 시작. PC 또는 앱이 꺼져 있으면 예약은 실행되지 않습니다.")
        self.refresh_all()
        self.tick()

    def page(self, name, subtitle):
        self.nav.addItem(name)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        title = QLabel(name)
        title.setStyleSheet("font-size:25px;font-weight:600;padding:8px 0")
        layout.addWidget(title)
        note = QLabel(subtitle)
        note.setWordWrap(True)
        layout.addWidget(note)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.pages.addWidget(scroll)
        return layout

    def button(self, layout, key, text, callback):
        button = QPushButton(text)
        button.setObjectName(key)
        self.buttons[key] = button
        def invoke():
            try:
                callback()
            except Exception as exc:
                self.notify(str(exc) if isinstance(exc, ValueError) else safe_error(exc), "ERROR")
        button.clicked.connect(invoke)
        layout.addWidget(button)
        return button

    def row(self, layout):
        row = QHBoxLayout()
        layout.addLayout(row)
        return row

    def build_dashboard(self):
        layout = self.page("대시보드", "작업 결과는 로컬에 저장됩니다. AI 초안은 검토 후 사용하세요.")
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("font-size:17px;background:white;padding:24px")
        layout.addWidget(self.summary)
        self.activity = QLabel("준비됨")
        self.activity.setWordWrap(True)
        layout.addWidget(self.activity)
        row = self.row(layout)
        self.button(row, "check_local", "무료 Mock 자동 작성 점검", self.check_local)
        self.button(row, "author_now", "저장된 설정으로 자동 작성", self.run_scheduled)
        self.button(layout, "open_local_output", "최근 자동 작성 결과 폴더 열기", self.open_local_output)
        self.local_result = QLabel()
        self.local_result.setWordWrap(True)
        self.local_result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.local_result)
        layout.addWidget(QLabel("1. 설정에서 ChatGPT 로그인 → 2. 모델 선택·Mock 해제·설정 저장 → 3. 주제 입력 후 글 생성\n서버 없이 글·ZIP을 저장합니다. Ubuntu 전달은 콘텐츠 출력에서 별도로 실행합니다."))
        self.button(layout, "refresh", "상태 새로고침", self.refresh_all)
        layout.addStretch()

    def build_settings(self):
        layout = self.page("설정", "설정 저장 후 적용됩니다. 빈 비밀정보 입력란은 기존 값을 유지합니다.")
        form = QFormLayout()
        layout.addLayout(form)
        self.server_url = QLineEdit(self.config.server_url)
        form.addRow(QLabel("AI Blog 서버: https://61.105.141.21:8001 · 같은 PC: http://127.0.0.1:8000\n서버 주소에는 /api/v1 경로를 넣지 마세요. ChatGPT 글쓰기에는 서버 연결이 필요 없습니다."))
        self.writer_provider = QComboBox()
        self.writer_provider.addItem("ChatGPT 구독 (Plus 등)", "chatgpt")
        self.writer_provider.addItem("OpenAI API (별도 과금)", "openai")
        self.writer_provider.setCurrentIndex(self.writer_provider.findData(self.config.writer_provider))
        form.addRow("글쓰기 연결", self.writer_provider)
        self.chatgpt_accounts = QComboBox()
        form.addRow("ChatGPT 계정", self.chatgpt_accounts)
        self.chatgpt_model = QComboBox()
        if self.config.chatgpt_model:
            self.chatgpt_model.addItem(self.config.chatgpt_model, self.config.chatgpt_model)
        form.addRow("ChatGPT 글 모델", self.chatgpt_model)
        self.mock_mode = QCheckBox("Mock 모드 (테스트 글만 생성 · 실제 ChatGPT 글쓰기는 체크 해제)")
        self.mock_mode.setChecked(self.config.mock)
        form.addRow("실행 모드", self.mock_mode)
        row = self.row(layout)
        self.button(row, "chatgpt_login", "Continue with ChatGPT", self.login_chatgpt)
        self.button(row, "chatgpt_models", "선택 계정 사용 · 모델 불러오기", self.load_chatgpt_models)
        self.button(row, "chatgpt_logout", "ChatGPT 로그아웃", self.logout_chatgpt)
        self.button(layout, "save_chatgpt_settings", "모델 선택 후 설정 저장", self.save_settings)
        self.button(layout, "chatgpt_usage", "ChatGPT 사용량 · 앱 한도 확인", lambda: QDesktopServices.openUrl(QUrl("https://chatgpt.com/settings/usage")))
        self.chatgpt_status = QLabel("로그인 시 브라우저에서 ChatGPT 구독 사용을 허용하세요. API 키 입력은 필요 없습니다.")
        self.chatgpt_status.setWordWrap(True)
        layout.addWidget(self.chatgpt_status)
        self.refresh_chatgpt_accounts()
        form = QFormLayout()
        layout.addLayout(form)
        self.device_id = QLineEdit(self.config.device_id)
        self.server_token = password_field()
        self.api_key = password_field()
        self.text_model = QLineEdit(self.config.text_model)
        self.image_model = QLineEdit(self.config.image_model)
        self.style = QLineEdit(self.config.style)
        self.rss = QPlainTextEdit(self.config.rss_urls)
        self.rss.setPlaceholderText("사용 권한이 있는 HTTPS RSS/Atom URL을 한 줄에 하나씩 입력")
        self.rss.setMaximumHeight(90)
        for label, widget in [("서버 주소", self.server_url), ("기기 ID", self.device_id),
                              ("서버 토큰", self.server_token), ("OpenAI API 키", self.api_key),
                              ("API 글 모델", self.text_model),
                              ("이미지 모델", self.image_model), ("글 스타일", self.style), ("뉴스 RSS", self.rss)]:
            form.addRow(label, widget)
        self.key_status = QLabel()
        form.addRow(self.key_status)
        row = self.row(layout)
        self.button(row, "save_settings", "설정 저장", self.save_settings)
        self.button(row, "delete_key", "API 키 삭제", lambda: self.delete_secret("openai"))
        self.button(row, "delete_token", "서버 토큰 삭제", lambda: self.delete_secret("server"))
        self.button(row, "wizard", "설정 마법사", self.open_wizard)
        self.button(layout, "diagnose_settings", "현재 입력값 진단 (통신·비용 없음)", self.diagnose_settings)
        self.button(layout, "use_shared_https", "AI Blog HTTPS 주소 입력 (8001)", self.use_shared_https)
        self.settings_diagnosis = QPlainTextEdit()
        self.settings_diagnosis.setReadOnly(True)
        self.settings_diagnosis.setMinimumHeight(180)
        layout.addWidget(self.settings_diagnosis)
        def provider_changed():
            is_api = self.writer_provider.currentData() == "openai"
            for widget in (self.api_key, self.text_model, self.image_model):
                widget.setEnabled(is_api)
        self.writer_provider.currentIndexChanged.connect(provider_changed)
        provider_changed()
        layout.addStretch()

    def diagnose_settings(self):
        self.settings_diagnosis.setPlainText(settings_report(
            self.server_url.text(), self.mock_mode.isChecked(),
            bool(self.api_key.text().strip() or self.vault.get("openai")),
            bool(self.server_token.text().strip() or self.vault.get("server")),
            self.writer_provider.currentData(), self.chatgpt_ready()))

    def chatgpt_ready(self):
        try:
            return self.services.chatgpt.connected()
        except Exception:
            return False

    def refresh_chatgpt_accounts(self):
        self.chatgpt_accounts.clear()
        self.chatgpt_accounts.addItem("새 ChatGPT 계정 연결", "")
        try:
            accounts, active = self.services.chatgpt.accounts()
            for key, label in accounts:
                self.chatgpt_accounts.addItem(label, key)
            self.chatgpt_accounts.setCurrentIndex(max(0, self.chatgpt_accounts.findData(active)))
        except Exception as exc:
            self.chatgpt_status.setText(safe_error(exc))

    def login_chatgpt(self):
        selected = self.chatgpt_accounts.currentData() or ""
        self.chatgpt_status.setText("브라우저에서 로그인하고 ChatGPT 구독 사용을 허용하세요. 최대 3분 기다립니다.")
        def complete(message):
            self.refresh_chatgpt_accounts()
            self.chatgpt_status.setText(message)
            self.writer_provider.setCurrentIndex(0)
        self.run_task("ChatGPT 로그인", lambda: self.services.chatgpt.login(selected), complete,
                      self.chatgpt_status.setText)

    def load_chatgpt_models(self):
        selected = self.chatgpt_accounts.currentData()
        def operation():
            self.services.chatgpt.select(selected)
            return self.services.chatgpt.models()
        def complete(models):
            self.chatgpt_model.clear()
            for slug, label in models:
                self.chatgpt_model.addItem(label, slug)
            index = self.chatgpt_model.findData(self.config.chatgpt_model)
            self.chatgpt_model.setCurrentIndex(max(0, index))
            self.chatgpt_status.setText("모델을 선택하고 Mock 모드를 해제한 뒤 설정 저장을 누르세요. 이미지 자동 생성은 해제하세요.")
        self.run_task("ChatGPT 모델 조회", operation, complete, self.chatgpt_status.setText)

    def logout_chatgpt(self):
        self.run_task("ChatGPT 로그아웃", self.services.chatgpt.logout, self.chatgpt_status.setText,
                      self.chatgpt_status.setText)

    def use_shared_https(self):
        self.server_url.setText("https://61.105.141.21:8001")
        self.diagnose_settings()
        self.notify("AI Blog 전용 HTTPS 주소를 입력했습니다. 설정 저장 → 서버 연결을 실행하세요.")

    def save_settings(self):
        config = copy.deepcopy(self.config)
        config.server_url, config.device_id = self.server_url.text().strip(), self.device_id.text().strip()
        config.mock = self.mock_mode.isChecked()
        config.writer_provider = self.writer_provider.currentData()
        config.chatgpt_model = self.chatgpt_model.currentData() or ""
        config.text_model, config.image_model = self.text_model.text().strip(), self.image_model.text().strip()
        config.style, config.rss_urls = self.style.text(), self.rss.toPlainText()
        config.validate()
        if self.api_key.text().strip():
            self.vault.set("openai", self.api_key.text().strip())
        if self.server_token.text().strip():
            self.vault.set("server", self.server_token.text().strip())
        config.initialized = True
        self.store.save_settings(config)
        self.config = config
        self.api_key.clear()
        self.server_token.clear()
        self.notify("설정을 저장했습니다.")
        self.refresh_all()

    def delete_secret(self, name):
        self.vault.set(name, "")
        (self.api_key if name == "openai" else self.server_token).clear()
        self.notify("저장된 비밀정보를 삭제했습니다.")
        self.refresh_all()

    def open_wizard(self):
        wizard = SetupWizard(self.store, self.vault, self)
        if wizard.exec() == QWizard.DialogCode.Accepted:
            self.config = self.store.settings()
            self.server_url.setText(self.config.server_url)
            self.device_id.setText(self.config.device_id)
            self.mock_mode.setChecked(self.config.mock)
            self.notify("설정 마법사 완료")
            self.refresh_all()

    def build_server(self):
        layout = self.page("서버 연결", "Phase 1 API를 사용합니다. Mock 모드도 서버 연결과 인증은 실제로 검사합니다.")
        self.connection = QLabel("확인 전")
        self.connection.setWordWrap(True)
        self.connection.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.connection)
        row = self.row(layout)
        self.button(row, "connect", "연결 / 이벤트 조회", self.connect_server)
        self.button(row, "send_event", "Mock 이벤트 전송", lambda: self.send_event(False))
        self.button(row, "flush", "대기 이벤트 재전송", lambda: self.send_event(True))
        self.events = QPlainTextEdit()
        self.events.setReadOnly(True)
        layout.addWidget(self.events, 1)

    def connect_server(self):
        config, token = copy.deepcopy(self.config), self.vault.get("server")
        self.connection.setText("연결 확인 중…")
        self.run_task("서버 연결", lambda: self.services.connect(config, token), self.connected,
                      lambda message: self.connection.setText("연결 실패\n" + message))

    def connected(self, events):
        self.connection.setText("ONLINE · 인증된 API 연결 확인 · " + utcnow())
        self.events.setPlainText(json.dumps(events, ensure_ascii=False, indent=2))

    def send_event(self, flush_only):
        config, token = copy.deepcopy(self.config), self.vault.get("server")
        self.run_task("이벤트 전송", lambda: self.services.send_mock(config, token, flush_only),
                      lambda count: self.connection.setText(f"서버가 {count}건을 확인했습니다."))

    def build_schedule(self):
        layout = self.page("예약 스케줄", "Asia/Seoul 기준. 앱이 실행 중일 때 초안을 생성합니다. 자동 발행하지 않습니다.")
        form = QFormLayout()
        layout.addLayout(form)
        self.schedule_times = QLineEdit(", ".join(self.config.times))
        self.schedule_topic = QLineEdit(self.config.topic)
        self.days = []
        days = QWidget()
        row = QHBoxLayout(days)
        for i, day in enumerate(["월", "화", "수", "목", "금", "토", "일"]):
            check = QCheckBox(day)
            check.setChecked(i in self.config.weekdays)
            self.days.append(check)
            row.addWidget(check)
        self.resume = QComboBox()
        self.resume.addItem("누락된 작업 건너뛰기", "skip")
        self.resume.addItem("앱 재시작 시 누락 작업 1회 실행", "once")
        self.resume.setCurrentIndex(0 if self.config.resume_policy == "skip" else 1)
        self.schedule_images = QCheckBox("초안과 이미지 함께 생성 (실제 모드는 API 비용 발생)")
        self.schedule_images.setChecked(self.config.scheduled_image)
        form.addRow("시간 (쉼표 구분)", self.schedule_times)
        form.addRow("요일", days)
        form.addRow("주제", self.schedule_topic)
        form.addRow("재개 정책", self.resume)
        form.addRow(self.schedule_images)
        self.next_run = QLabel()
        self.next_run.setWordWrap(True)
        layout.addWidget(self.next_run)
        row = self.row(layout)
        self.button(row, "save_schedule", "예약 설정 저장", self.save_schedule)
        self.button(row, "toggle_schedule", "예약 ON / OFF", self.toggle_schedule)
        self.button(row, "run_schedule", "저장된 예약 작업 지금 실행", self.run_scheduled)
        layout.addStretch()

    def save_schedule(self):
        config = copy.deepcopy(self.config)
        config.times = [s.strip() for s in self.schedule_times.text().split(",") if s.strip()]
        config.weekdays = [i for i, check in enumerate(self.days) if check.isChecked()]
        config.topic = self.schedule_topic.text().strip()
        config.resume_policy = self.resume.currentData()
        config.scheduled_image = self.schedule_images.isChecked()
        self.store.save_settings(config)
        self.config = config
        self.engine.apply(config)
        self.notify("예약 설정 저장 완료")
        self.tick()

    def toggle_schedule(self):
        self.save_schedule()
        self.config.schedule_enabled = not self.config.schedule_enabled
        self.store.save_settings(self.config)
        self.engine.apply(self.config)
        self.notify("예약 " + ("ON" if self.config.schedule_enabled else "OFF"))
        self.tick()

    def run_scheduled(self):
        if self.busy:
            self.notify("진행 중인 작업이 있어 이번 예약을 건너뜁니다.", "WARNING")
            return
        config = copy.deepcopy(self.config)
        key = "" if config.mock else self.vault.get("openai")
        self.start_authoring(config, key)

    def check_local(self):
        config = copy.deepcopy(self.config)
        config.mock, config.scheduled_image = True, True
        self.start_authoring(config, "")

    def open_local_output(self):
        result = self.store.get("last_authoring_run", {})
        path = Path(result.get("path", ""))
        if result.get("status") != "completed" or not path.is_file():
            raise ValueError("완료된 자동 작성 ZIP이 없습니다. 먼저 Mock 점검 또는 자동 작성을 실행하세요.")
        self.browser(QUrl.fromLocalFile(str(path.parent.resolve())))

    def start_authoring(self, config, key):
        def completed(result):
            self.display_article(result["article"])
            if result["image"]:
                self.display_image(result["image"])
            self.store.put("last_schedule_run", utcnow())
        self.run_task("자동 작성 · 로컬 파일 저장", lambda: author_locally(
            self.services, config, key, self.active_task.signals.progress.emit), completed)

    def build_news(self):
        layout = self.page("뉴스 수집", "RSS/Atom 제목·요약·출처를 수집합니다. 신뢰도와 사실 여부는 자동 보증하지 않습니다.")
        row = self.row(layout)
        self.button(row, "collect_news", "뉴스 수집", self.collect_news)
        self.button(row, "open_source", "선택 출처 열기", self.open_source)
        self.button(row, "use_news", "선택 뉴스를 글쓰기로", self.use_news)
        self.news_table = QTableWidget(0, 3)
        self.news_table.setHorizontalHeaderLabels(["제목", "발행 시각", "출처"])
        self.news_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.news_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.news_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.news_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.news_table.itemSelectionChanged.connect(self.show_news_detail)
        layout.addWidget(self.news_table, 1)
        self.news_detail = QPlainTextEdit()
        self.news_detail.setReadOnly(True)
        self.news_detail.setMaximumHeight(130)
        layout.addWidget(self.news_detail)

    def collect_news(self):
        config = copy.deepcopy(self.config)
        self.run_task("뉴스 수집", lambda: self.services.collect_news(config), self.display_news)

    def display_news(self, items):
        self.news_items = items
        self.news_table.setRowCount(len(items))
        for row, item in enumerate(items):
            for col, key in enumerate(("title", "published", "url")):
                self.news_table.setItem(row, col, QTableWidgetItem(item[key]))
        if items:
            self.news_table.selectRow(0)

    def selected_news(self):
        row = self.news_table.currentRow()
        if row < 0 or row >= len(self.news_items):
            raise ValueError("뉴스를 먼저 수집하고 선택하세요.")
        return self.news_items[row]

    def show_news_detail(self):
        row = self.news_table.currentRow()
        if 0 <= row < len(self.news_items):
            self.news_detail.setPlainText(self.news_items[row]["summary"])

    def open_source(self):
        self.open_url(self.selected_news()["url"])

    def use_news(self):
        self.source = self.selected_news()
        self.topic.setText(self.source["title"])
        self.source_label.setText("출처: " + self.source["url"])
        self.review_source.setChecked(False)
        self.nav.setCurrentRow(5)

    def build_writer(self):
        layout = self.page("AI 글쓰기", "ChatGPT 글쓰기: 설정에서 로그인 → 모델 선택 → Mock 해제 → 설정 저장. 서버 연결은 필요 없습니다.")
        self.writer_status = QLabel()
        self.writer_status.setWordWrap(True)
        layout.addWidget(self.writer_status)
        self.topic = QLineEdit(self.config.topic)
        self.topic.setPlaceholderText("글의 주제")
        layout.addWidget(self.topic)
        self.source = None
        self.source_label = QLabel("출처 없음 · 일반 설명 초안")
        self.source_label.setWordWrap(True)
        layout.addWidget(self.source_label)
        self.review_source = QCheckBox("선택한 출처와 요약을 검토했습니다")
        layout.addWidget(self.review_source)
        row = self.row(layout)
        self.button(row, "write_article", "AI 글 생성", self.write_article)
        self.button(row, "clear_source", "출처 선택 해제", self.clear_source)
        self.button(row, "copy_article", "본문 복사", self.copy_article)
        self.button(row, "export_article", "텍스트 저장", self.export_article)
        self.history = QComboBox()
        self.history.currentIndexChanged.connect(self.load_article)
        layout.addWidget(self.history)
        self.article_view = QPlainTextEdit()
        self.article_view.setReadOnly(True)
        layout.addWidget(self.article_view, 1)

    def clear_source(self):
        self.source = None
        self.source_label.setText("출처 없음 · 일반 설명 초안")
        self.review_source.setChecked(False)

    def write_article(self):
        if self.source and not self.review_source.isChecked():
            raise ValueError("선택한 출처를 검토한 후 확인란을 선택하세요.")
        config, key, topic = copy.deepcopy(self.config), self.vault.get("openai"), self.topic.text()
        sources = [copy.deepcopy(self.source)] if self.source else []
        self.run_task("AI 글 생성", lambda: self.services.write_article(config, key, topic, sources), self.display_article)

    def display_article(self, article):
        self.article = article
        self.article_view.setPlainText(article_text(article))
        self.refresh_history(article["id"])
        self.refresh_output()

    def refresh_history(self, selected=None):
        self.history.blockSignals(True)
        self.history.clear()
        for article in self.store.articles():
            self.history.addItem(article["title"], article)
            if selected == article["id"]:
                self.history.setCurrentIndex(self.history.count()-1)
        self.history.blockSignals(False)

    def load_article(self):
        article = self.history.currentData()
        if article:
            self.article = article
            self.article_view.setPlainText(article_text(article))
            self.refresh_output()

    def build_output(self):
        layout = self.page("콘텐츠 출력", "글쓰기 화면에서 선택한 초안의 출력입니다. 첫 이미지는 썸네일, 이후 이미지는 섹션 뒤에 순서대로 배치합니다.")
        self.output_title = QLabel("글을 먼저 생성하거나 선택하세요.")
        self.output_title.setWordWrap(True)
        layout.addWidget(self.output_title)
        row = self.row(layout)
        self.button(row, "add_latest_image", "최근 생성 이미지 추가", self.add_latest_image)
        self.button(row, "add_image_files", "이미지 파일 추가", self.add_image_files)
        self.button(row, "image_up", "위로", lambda: self.move_output_image(-1))
        self.button(row, "image_down", "아래로", lambda: self.move_output_image(1))
        self.button(row, "remove_image", "목록에서 제거", self.remove_output_image)
        self.output_images = QListWidget()
        self.output_images.setMaximumHeight(140)
        self.output_images.currentRowChanged.connect(self.select_output_image)
        # Override navigation styling for an ordinary light image list.
        self.output_images.setStyleSheet("QListWidget {background:white;color:#17283f;padding:0;font-size:12px;} QListWidget::item {padding:5px;} QListWidget::item:selected {background:#c6e9e7;color:#17283f;}")
        layout.addWidget(self.output_images)
        row = self.row(layout)
        self.image_caption = QLineEdit()
        self.image_caption.setPlaceholderText("선택 이미지 설명")
        row.addWidget(self.image_caption, 1)
        self.button(row, "save_caption", "설명 저장", self.save_image_caption)
        row = self.row(layout)
        self.button(row, "preview_html", "HTML 미리보기", self.preview_html)
        self.button(row, "copy_rich", "서식 포함 전체 복사", self.copy_rich)
        self.button(row, "export_html", "HTML 저장", lambda: self.export_publication("html"))
        self.button(row, "export_docx", "Word 저장", lambda: self.export_publication("docx"))
        self.button(row, "export_package", "ZIP 패키지 만들기", lambda: self.export_publication("zip"))
        row = self.row(layout)
        self.button(row, "manual_upload", "수동 발행 패키지 생성·업로드", self.upload_manual)
        self.button(row, "failed_upload", "발행 실패 기록·패키지 전달", lambda: self.upload_manual(True))
        self.button(row, "retry_packages", "대기 업로드 재시도", self.retry_packages)
        layout.addWidget(QLabel("자동 발행 비활성 · 실패 기록은 사용자 신고입니다. 재시도는 기존 패키지를 사용합니다."))
        self.output_preview = HtmlPreview()
        self.output_preview.setMinimumHeight(220)
        layout.addWidget(self.output_preview, 1)

    def require_article(self):
        if not self.article:
            raise ValueError("글쓰기 화면에서 글을 먼저 생성하거나 선택하세요.")

    def upload_manual(self, failed=False):
        from .manual import ManualHandoff
        self.require_article()
        article, config = copy.deepcopy(self.article), copy.deepcopy(self.config)
        token = self.vault.get("server")
        def operation():
            handoff = ManualHandoff(self.services)
            path = handoff.prepare(config, article, failed)
            result = handoff.upload(config, token, path)
            self.services.send_mock(config, token, flush_only=True)
            return result
        self.run_task("수동 발행 패키지 전달", operation, lambda r: self.notify("업로드 완료 · 만료: " + r["expires_at"]))

    def retry_packages(self):
        from .manual import ManualHandoff
        config, token = copy.deepcopy(self.config), self.vault.get("server")
        def operation():
            result = ManualHandoff(self.services).retry(config, token)
            self.services.send_mock(config, token, flush_only=True)
            return result
        self.run_task("대기 업로드 재시도", operation, lambda r: self.notify(f"대기 패키지 {len(r)}개 전달 완료"))

    def refresh_output(self, selected=0):
        if not hasattr(self, "output_images"):
            return
        self.output_images.clear()
        self.output_preview.clear()
        if not self.article:
            return
        self.output_title.setText(self.article["title"])
        for i, image in enumerate(self.article.get("images", [])):
            position = "썸네일" if i == 0 else f"본문 이미지 {i}"
            self.output_images.addItem(f"{i+1}. {position} · {image['caption']}")
        if self.output_images.count():
            self.output_images.setCurrentRow(min(selected, self.output_images.count()-1))
        else:
            self.image_caption.clear()

    def select_output_image(self, row):
        if self.article and 0 <= row < len(self.article.get("images", [])):
            self.image_caption.setText(self.article["images"][row]["caption"])

    def attach_images(self, paths, disclosure="사용자 제공 이미지", caption=""):
        self.require_article()
        article = copy.deepcopy(self.article)
        if len(article.get("images", [])) + len(paths) > MAX_IMAGES:
            raise ValueError("글 하나에 이미지는 최대 30개입니다.")
        def operation():
            return [import_image(path, self.store.directory, caption, disclosure) for path in paths]
        def completed(images):
            article.setdefault("images", []).extend(images)
            self.store.save_article(article)
            self.display_article(article)
        self.run_task("출력 이미지 추가", operation, completed)

    def add_latest_image(self):
        if not self.image:
            raise ValueError("이미지 생성 화면에서 이미지를 먼저 생성하세요.")
        self.attach_images([self.image["path"]], self.image["disclosure"], self.image.get("prompt", ""))

    def add_image_files(self):
        self.require_article()
        paths, _ = QFileDialog.getOpenFileNames(self, "출력 이미지 선택", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if paths:
            self.attach_images(paths)

    def image_index(self):
        self.require_article()
        index = self.output_images.currentRow()
        if not 0 <= index < len(self.article.get("images", [])):
            raise ValueError("목록에서 이미지를 선택하세요.")
        return index

    def persist_images(self, selected=0):
        self.store.save_article(self.article)
        self.refresh_history(self.article["id"])
        self.refresh_output(selected)
        self.notify("이미지 순서와 설명을 초안에 저장했습니다.")

    def move_output_image(self, delta):
        index = self.image_index()
        target = index + delta
        images = self.article["images"]
        if 0 <= target < len(images):
            images[index], images[target] = images[target], images[index]
            self.persist_images(target)

    def remove_output_image(self):
        index = self.image_index()
        self.article["images"].pop(index)
        self.persist_images(max(0, index-1))

    def save_image_caption(self):
        index = self.image_index()
        self.article["images"][index]["caption"] = self.image_caption.text().strip()
        self.persist_images(index)

    def preview_html(self):
        self.require_article()
        article = copy.deepcopy(self.article)
        self.run_task("HTML 미리보기", lambda: Publication(article).html(), self.output_preview.setHtml)

    def copy_rich(self):
        self.require_article()
        article = copy.deepcopy(self.article)
        # Publish clipboard formats on the GUI thread after image preparation.
        self.run_task("서식 포함 전체 복사", lambda: Publication(article),
                      lambda output: copy_publication(output, int(self.winId())))

    def export_publication(self, kind):
        self.require_article()
        descriptions = {"html": "HTML (*.html)", "docx": "Word (*.docx)", "zip": "ZIP (*.zip)"}
        path, _ = QFileDialog.getSaveFileName(self, "콘텐츠 출력", f"article.{kind}", descriptions[kind])
        if not path:
            return
        article = copy.deepcopy(self.article)
        def operation():
            output = Publication(article)
            data = output.html().encode("utf-8") if kind == "html" else output.docx() if kind == "docx" else output.package()
            atomic_write(path, data)
            return path
        self.run_task("콘텐츠 " + kind.upper() + " 저장", operation, lambda _: None)

    def copy_article(self):
        if not self.article:
            raise ValueError("글을 먼저 생성하세요.")
        QApplication.clipboard().setText(article_text(self.article))
        self.notify("본문을 일반 텍스트로 복사했습니다.")

    def export_article(self):
        if not self.article:
            raise ValueError("글을 먼저 생성하세요.")
        path, _ = QFileDialog.getSaveFileName(self, "초안 저장", "article.txt", "Text (*.txt)")
        if path:
            Path(path).write_text(article_text(self.article), encoding="utf-8")
            self.notify("초안 텍스트 저장 완료")

    def build_images(self):
        layout = self.page("이미지 생성", "실제 생성에는 API 키가 필요합니다. Mock 모드는 테스트 PNG를 만듭니다. 서버 연결은 필요 없습니다.")
        self.image_prompt = QLineEdit("AI 기술과 일상생활을 설명하는 일러스트")
        layout.addWidget(self.image_prompt)
        self.image_size = QComboBox()
        self.image_size.addItems(["1024x1024", "1536x1024", "1024x1536"])
        layout.addWidget(self.image_size)
        row = self.row(layout)
        self.button(row, "generate_image", "이미지 생성 / 재시도", self.generate_image)
        self.button(row, "save_image", "이미지 다른 이름으로 저장", self.export_image)
        self.image_label = QLabel("생성한 이미지가 여기에 표시됩니다.")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(300)
        layout.addWidget(self.image_label, 1)
        self.image_info = QLabel()
        self.image_info.setWordWrap(True)
        layout.addWidget(self.image_info)

    def generate_image(self):
        config, key = copy.deepcopy(self.config), self.vault.get("openai")
        prompt, size = self.image_prompt.text(), self.image_size.currentText()
        self.run_task("이미지 생성", lambda: self.services.generate_image(config, key, prompt, size), self.display_image)

    def display_image(self, image):
        pixmap = QPixmap(image["path"])
        if pixmap.isNull():
            raise ValueError("이미지 파일을 읽을 수 없습니다.")
        self.image = image
        self.image_label.setPixmap(pixmap.scaled(620, 360, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.image_info.setText(image["disclosure"] + "\n" + image["path"])

    def export_image(self):
        if not self.image:
            raise ValueError("이미지를 먼저 생성하세요.")
        path, _ = QFileDialog.getSaveFileName(self, "PNG 저장", "illustration.png", "PNG (*.png)")
        if path:
            if Path(path).resolve() != Path(self.image["path"]).resolve():
                shutil.copyfile(self.image["path"], path)
            self.notify("이미지 저장 완료")

    def build_account(self):
        layout = self.page("로그인 상태", "공식 브라우저 로그인만 엽니다. 네이버 비밀번호·쿠키를 읽거나 저장하지 않습니다.")
        self.login_label = QLabel()
        self.login_label.setWordWrap(True)
        layout.addWidget(self.login_label)
        self.login_state = QComboBox()
        self.login_state.addItems(["확인 불가", "성공", "실패", "만료", "로그아웃"])
        layout.addWidget(self.login_state)
        row = self.row(layout)
        self.button(row, "naver_login", "네이버 공식 로그인 열기", self.open_login)
        self.button(row, "record_login", "사용자 확인 상태 기록", self.record_login)
        self.button(row, "reset_login", "확인 불가로 초기화", self.reset_login)
        layout.addWidget(QLabel("기록은 사용자 신고 상태입니다. 자동 인증 검증 또는 자동 발행을 뜻하지 않습니다."))
        layout.addStretch()

    def open_url(self, url):
        if not self.browser(QUrl(url)):
            raise ValueError("기본 브라우저를 열 수 없습니다.")

    def open_login(self):
        self.open_url("https://nid.naver.com/nidlogin.login")
        self.notify("공식 로그인 화면을 열었습니다. 실제 로그인 결과는 확인하지 않았습니다.")

    def record_login(self):
        self.services.record_login(self.config, self.login_state.currentText())
        self.notify("사용자가 확인한 로그인 상태를 로컬에 기록했습니다.")
        self.refresh_all()

    def reset_login(self):
        self.login_state.setCurrentIndex(0)
        self.record_login()

    def build_logs(self):
        layout = self.page("로그 관리", "최근 2,000건을 로컬 DB에 보관합니다. API 키·서버 토큰·HTTP 응답 본문은 기록하지 않습니다.")
        self.log_level = QComboBox()
        self.log_level.addItems(["ALL", "INFO", "WARNING", "ERROR"])
        self.log_level.currentTextChanged.connect(self.refresh_logs)
        layout.addWidget(self.log_level)
        row = self.row(layout)
        self.button(row, "refresh_logs", "로그 새로고침", self.refresh_logs)
        self.button(row, "export_logs", "로그 내보내기", self.export_logs)
        self.button(row, "clear_logs", "로컬 로그 비우기", self.clear_logs)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, 1)

    def refresh_logs(self):
        rows = self.store.logs(self.log_level.currentText())
        self.log_view.setPlainText("\n".join(f"{at} [{level}] {message}" for at, level, message in rows))

    def export_logs(self):
        path, _ = QFileDialog.getSaveFileName(self, "로그 저장", "desktop-logs.txt", "Text (*.txt)")
        if path:
            Path(path).write_text(self.log_view.toPlainText(), encoding="utf-8")
            self.notify("로그 내보내기 완료")

    def clear_logs(self):
        self.store.clear_logs()
        self.refresh_logs()
        self.statusBar().showMessage("로컬 로그를 비웠습니다.")

    def notify(self, message, level="INFO"):
        self.store.log(level, message)
        self.statusBar().showMessage(message)
        self.activity.setText(message)
        self.refresh_logs()

    def run_task(self, name, operation, completed, failed=None):
        if self.busy:
            self.notify("현재 작업이 끝난 후 다시 실행하세요.", "WARNING")
            return
        self.busy = True
        for button in self.buttons.values():
            button.setEnabled(False)
        self.notify(name + " 진행 중…")
        task = Task(operation)
        self.active_task = task
        def finish():
            self.busy = False
            for button in self.buttons.values():
                button.setEnabled(True)
            self.active_task = None
            self.refresh_summary()
        def success(value):
            try:
                completed(value)
                self.notify(name + " 완료")
                if name == "AI 글 생성":
                    self.writer_status.setText("테스트 Mock 글 생성 완료 · 실제 AI 결과가 아닙니다." if value.get("mock") else "실제 AI 글 생성 완료")
            except Exception as exc:
                self.notify(safe_error(exc), "ERROR")
            finally:
                finish()
        def failure(message):
            if failed:
                failed(message)
            if name == "AI 글 생성":
                self.writer_status.setText("글 생성 실패: " + message)
            self.notify(name + ": " + message, "ERROR")
            finish()
        task.signals.done.connect(success)
        task.signals.failed.connect(failure)
        task.signals.progress.connect(lambda message: self.activity.setText("자동 작성: " + message))
        self.pool.start(task)

    def refresh_summary(self):
        key = bool(self.vault.get("openai"))
        mode = "MOCK" if self.config.mock else ("실제 OpenAI API" if key else "자동 작성 준비 필요 · API 키 없음")
        if not self.config.mock and self.config.writer_provider == "chatgpt":
            mode = "ChatGPT 구독 · " + ("로그인됨" if self.chatgpt_ready() else "설정에서 로그인 필요")
        news = "MOCK" if self.config.mock else "실제 RSS"
        self.summary.setText(f"AI: {mode}  |  뉴스: {news}\n\n저장된 초안: {len(self.store.articles())}건\n예약: {'ON' if self.config.schedule_enabled else 'OFF'} · Asia/Seoul\n\n네이버 자동 발행: 미지원 · 모든 결과는 검토용 초안")
        self.key_status.setText(f"글쓰기: {mode} / API 키: {'저장됨' if key else '없음 (ChatGPT 모드는 불필요)'} / 서버 토큰: {'저장됨' if self.vault.get('server') else '없음 · 로컬 작성 가능'}")
        result = self.store.get("last_authoring_run", {})
        mode_label = "Mock 점검" if result.get("mock") else "실제 AI"
        self.local_result.setText(
            f"최근 자동 작성 ({mode_label}): {result.get('stage', '미실행')}\n"
            f"상태: {result.get('status', '대기')}\n{result.get('path', '')}\n"
            "서버 연결은 로컬 자동 작성의 필수 조건이 아닙니다.")

    def refresh_all(self):
        self.refresh_summary()
        self.diagnose_settings()
        self.writer_status.setText("Mock 모드: 테스트 글만 생성합니다." if self.config.mock else
                                   ("실제 AI 모드 준비됨 · 서버 연결 불필요" if self.vault.get("openai") else "API 키 없음: 설정에 키를 저장하세요."))
        if not self.config.mock and self.config.writer_provider == "chatgpt":
            self.writer_status.setText("ChatGPT 구독 글쓰기 · " + ("로그인됨" if self.chatgpt_ready() else "설정에서 ChatGPT 로그인 필요"))
        self.refresh_logs()
        self.refresh_history(self.article["id"] if self.article else None)
        if not self.article:
            self.load_article()
        if not self.news_items:
            self.display_news(self.store.news())
        if not self.image:
            image = self.store.get("last_image")
            if image and Path(image["path"]).exists():
                self.display_image(image)
        state = self.store.get("naver_status", {"state": "확인 불가", "at": "미확인", "source": "자동 검증 미지원"})
        self.login_label.setText(f"상태: {state['state']}\n마지막 기록: {state['at']}\n근거: {state['source']}")

    def tick(self):
        self.store.put("last_seen", utcnow())
        runs = self.engine.next_runs()
        self.next_run.setText("예약 ON · 다음 실행:\n" + "\n".join(runs) if runs else "예약 OFF")
        self.refresh_summary()

    def closeEvent(self, event):
        if self.busy:
            self.statusBar().showMessage("작업 완료 후 종료하세요. 네트워크 요청에는 시간 제한이 있습니다.")
            event.ignore()
            return
        self.heartbeat.stop()
        self.engine.stop()
        self.pool.waitForDone()
        self.store.put("last_seen", utcnow())
        self.store.log("INFO", "GUI 종료. 종료 중에는 예약 작업이 실행되지 않습니다.")
        event.accept()
