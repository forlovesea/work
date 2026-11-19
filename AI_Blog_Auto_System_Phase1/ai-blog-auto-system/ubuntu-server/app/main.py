import asyncio
import json
import os
import secrets
import sqlite3
import uuid
from contextlib import asynccontextmanager, closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator
from .packages import PackageStore, install_routes, utcnow, MAX_BYTES
from .mobile import MobileService, install_mobile, firebase_sender
from .manual import install_manual

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
EVENT_TYPES = {
    "PC_ONLINE", "PC_OFFLINE", "NAVER_LOGIN_SUCCESS", "NAVER_LOGIN_FAILED",
    "NAVER_LOGIN_EXPIRED", "CONTENT_GENERATED", "IMAGE_GENERATED", "PUBLISH_STARTED",
    "PUBLISH_SUCCESS", "PUBLISH_FAILED", "PUBLISH_UNCONFIRMED", "MANUAL_PUBLISH_REQUIRED",
    "PACKAGE_UPLOAD_SUCCESS", "PACKAGE_UPLOAD_FAILED", "STATISTICS_UPDATED", "SERVER_ERROR",
    "MOCK_PUBLISH_SUCCESS",
    "MANUAL_PUBLISH_COMPLETED",
    "PACKAGE_EXPIRING_6H", "PACKAGE_EXPIRING_1H", "PACKAGE_DELETED",
}


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    device_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    event_type: str
    occurred_at: AwareDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_type")
    @classmethod
    def known_type(cls, value):
        if value not in EVENT_TYPES:
            raise ValueError("Unknown event type")
        return value

    @field_validator("payload")
    @classmethod
    def bounded_payload(cls, value):
        if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > 16384:
            raise ValueError("Payload exceeds 16 KiB")
        return value


def create_app(db_path=None, device_token=None, *, package_dir=None, clock=utcnow,
               max_package_bytes=None, maintenance_interval=300, push_sender=None):
    path = Path(db_path or os.getenv("BLOG_DB_PATH", "./blog_events.sqlite3"))
    token = device_token if device_token is not None else os.getenv("BLOG_DEVICE_TOKEN", "")
    @asynccontextmanager
    async def lifespan(application):
        stop = asyncio.Event()
        task = asyncio.create_task(store.maintenance_loop(maintenance_interval, stop))
        push_task = asyncio.create_task(mobile.push_loop(stop))
        try:
            yield
        finally:
            stop.set()
            await task
            await push_task

    application = FastAPI(title="AI Blog Event Server", version="0.5.0", lifespan=lifespan)

    def admin_auth(x_device_token: str | None = Header(default=None)):
        if not token or not x_device_token or not secrets.compare_digest(
            x_device_token.encode(), token.encode()
        ):
            raise HTTPException(401, "Invalid device token")

    def auth(x_device_token: str | None = Header(default=None)):
        try:
            admin_auth(x_device_token)
        except HTTPException:
            mobile.verify(x_device_token)

    def connect():
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("CREATE TABLE IF NOT EXISTS events (event_id TEXT PRIMARY KEY, "
                   "device_id TEXT NOT NULL, event_type TEXT NOT NULL, occurred_at TEXT NOT NULL, "
                   "payload TEXT NOT NULL, received_at TEXT NOT NULL)")
        db.commit()
        return db

    store = PackageStore(connect, package_dir or os.getenv("BLOG_PACKAGE_DIR") or path.parent / "packages",
                         clock, max_package_bytes if max_package_bytes is not None else
                         int(os.getenv("BLOG_PACKAGE_MAX_BYTES", str(MAX_BYTES))))
    if store.max_bytes <= 0 or maintenance_interval <= 0:
        raise ValueError("Package limit and maintenance interval must be positive")
    application.state.packages = store
    mobile = MobileService(connect, clock, push_sender or firebase_sender())
    application.state.mobile = mobile
    install_mobile(application, mobile, admin_auth, auth)
    install_routes(application, store, auth, admin_auth)
    install_manual(application, store, auth)

    @application.get("/api/v1/health")
    def health():
        with closing(connect()) as db:
            db.execute("SELECT 1").fetchone()
        return {"status": "ok", "version": "0.5.0"}

    @application.post("/api/v1/events", dependencies=[Depends(admin_auth)])
    def post_event(event: Event):
        values = (str(event.event_id), event.device_id, event.event_type,
                  event.occurred_at.astimezone(timezone.utc).isoformat(),
                  json.dumps(event.payload, ensure_ascii=False, sort_keys=True))
        with closing(connect()) as db, db:
            cursor = db.execute("INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?)",
                                (*values, datetime.now(timezone.utc).isoformat()))
            inserted = cursor.rowcount > 0
            if not inserted:
                existing = db.execute("SELECT * FROM events WHERE event_id=?", (values[0],)).fetchone()
                same = (existing["device_id"] == event.device_id
                        and existing["event_type"] == event.event_type
                        and datetime.fromisoformat(existing["occurred_at"]) == event.occurred_at
                        and json.loads(existing["payload"]) == event.payload)
                if not same:
                    raise HTTPException(409, "Event UUID already has different content")
        return {"event_id": str(event.event_id), "accepted": True, "new": inserted}

    @application.get("/api/v1/events", dependencies=[Depends(auth)])
    def get_events(limit: int = Query(20, ge=1, le=100),
                   after: int | None = Query(None, ge=0)):
        # SQLite rowid is a stable cursor while events are append-only in Phase 1.
        with closing(connect()) as db:
            if after is None:
                rows = db.execute("SELECT rowid AS sequence, * FROM events ORDER BY rowid DESC LIMIT ?",
                                  (limit,)).fetchall()
            else:
                rows = db.execute("SELECT rowid AS sequence, * FROM events WHERE rowid>? "
                                  "ORDER BY rowid ASC LIMIT ?", (after, limit)).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]

    return application


app = create_app()
