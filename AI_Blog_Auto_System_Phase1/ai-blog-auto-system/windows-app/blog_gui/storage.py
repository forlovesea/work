import json
import os
import re
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from send_mock_event import validate_url


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def data_directory():
    return Path(os.getenv("BLOG_GUI_DATA_DIR", str(Path(os.getenv("LOCALAPPDATA", Path.home())) / "AI Blog Auto System")))


@dataclass
class Settings:
    initialized: bool = False
    server_url: str = "http://127.0.0.1:8000"
    device_id: str = "WINDOWS-DESKTOP"
    mock: bool = True
    text_model: str = "gpt-4.1-mini"
    writer_provider: str = "openai"
    chatgpt_model: str = ""
    image_model: str = "gpt-image-1"
    style: str = "사실과 출처를 명확히 구분하는 친절한 한국어 설명"
    rss_urls: str = ""
    topic: str = "AI 기술과 일상생활"
    times: list[str] = field(default_factory=lambda: ["08:00", "12:30", "19:00", "23:30"])
    weekdays: list[int] = field(default_factory=lambda: list(range(7)))
    schedule_enabled: bool = False
    resume_policy: str = "skip"
    scheduled_image: bool = False

    def validate(self):
        if self.writer_provider not in {"openai", "chatgpt"}:
            raise ValueError("글쓰기 연결 방식을 선택하세요.")
        self.server_url = validate_url(self.server_url)
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", self.device_id):
            raise ValueError("기기 ID는 영문, 숫자, 점, 밑줄, 하이픈 1~100자입니다.")
        if not self.text_model.strip() or not self.image_model.strip():
            raise ValueError("모델 이름을 입력하세요.")
        if not self.topic.strip():
            raise ValueError("예약 작업 주제를 입력하세요.")
        if not self.times or len(set(self.times)) != len(self.times):
            raise ValueError("예약 시간은 비어 있거나 중복될 수 없습니다.")
        if any(not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", t) for t in self.times):
            raise ValueError("예약 시간을 HH:MM 형식으로 입력하세요.")
        if not self.weekdays or any(d not in range(7) for d in self.weekdays):
            raise ValueError("하나 이상의 요일을 선택하세요.")
        if self.resume_policy not in {"skip", "once"}:
            raise ValueError("잘못된 재개 정책입니다.")


class Vault:
    """Force Windows Credential Manager; never fall back to a plaintext backend."""
    def __init__(self, namespace="AI Blog Auto System"):
        self.namespace = namespace
        self.backend = None
        if os.name == "nt":
            from keyring.backends.Windows import WinVaultKeyring
            self.backend = WinVaultKeyring()

    def get(self, name):
        if self.backend is None:
            return ""
        return self.backend.get_password(self.namespace, name) or ""

    def set(self, name, value):
        if self.backend is None:
            raise ValueError("비밀정보 저장은 Windows Credential Manager가 필요합니다.")
        try:
            if value:
                self.backend.set_password(self.namespace, name, value)
            elif self.get(name):
                self.backend.delete_password(self.namespace, name)
        except Exception:
            raise ValueError("Windows 자격증명 저장소를 사용할 수 없습니다. 로그인된 Windows 사용자 세션에서 실행하세요. 비밀정보를 평문으로 저장하지 않았습니다.") from None


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "desktop.sqlite3"
        with closing(self.connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS articles (id TEXT PRIMARY KEY, created TEXT, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS news (url TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, created TEXT, level TEXT, message TEXT);
            """)

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def get(self, key, default=None):
        with closing(self.connect()) as db:
            row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key, value):
        with closing(self.connect()) as db, db:
            db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, json.dumps(value, ensure_ascii=False)))

    def settings(self):
        raw = self.get("config", {})
        # Existing API configuration remains available, but the UI starts on the
        # requested subscription path until the user explicitly saves a choice.
        raw.setdefault("writer_provider", "chatgpt")
        return Settings(**{k: v for k, v in raw.items() if k in Settings.__dataclass_fields__})

    def save_settings(self, settings):
        settings.validate()
        self.put("config", asdict(settings))

    def log(self, level, message):
        # Only pass application-authored messages, never HTTP exception bodies.
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO logs(created,level,message) VALUES (?,?,?)", (utcnow(), level, message))
            db.execute("DELETE FROM logs WHERE id NOT IN (SELECT id FROM logs ORDER BY id DESC LIMIT 2000)")

    def logs(self, level="ALL"):
        with closing(self.connect()) as db:
            return db.execute("SELECT created,level,message FROM logs WHERE (?='ALL' OR level=?) ORDER BY id DESC", (level, level)).fetchall()

    def clear_logs(self):
        with closing(self.connect()) as db, db:
            db.execute("DELETE FROM logs")

    def save_news(self, items):
        with closing(self.connect()) as db, db:
            for item in items:
                db.execute("INSERT OR REPLACE INTO news VALUES (?,?)", (item["url"], json.dumps(item, ensure_ascii=False)))

    def news(self):
        with closing(self.connect()) as db:
            return [json.loads(r[0]) for r in db.execute("SELECT body FROM news ORDER BY rowid DESC LIMIT 100")]

    def save_article(self, article):
        with closing(self.connect()) as db, db:
            db.execute("INSERT OR REPLACE INTO articles VALUES (?,?,?)", (article["id"], article["created_at"], json.dumps(article, ensure_ascii=False)))

    def articles(self):
        with closing(self.connect()) as db:
            return [json.loads(r[0]) for r in db.execute("SELECT body FROM articles ORDER BY created DESC LIMIT 100")]

    def article_by_signature(self, signature):
        # Search all persisted drafts, not just the 100 items displayed in history.
        with closing(self.connect()) as db:
            for row in db.execute("SELECT body FROM articles"):
                article = json.loads(row[0])
                if article.get("signature") == signature:
                    return article
        return None
