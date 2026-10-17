from __future__ import annotations

import secrets
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RuleError(ValueError):
    pass


@dataclass
class Participant:
    id: str
    name: str
    token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    created: float = field(default_factory=time.monotonic)
    mic: bool = False
    camera: bool = False
    sharing: bool = False
    connected: bool = False
    ready: bool = False
    ws: Any = None
    send_lock: Any = None
    publisher: Any = None
    subscriptions: dict = field(default_factory=dict)
    tracks: dict = field(default_factory=dict)
    tasks: list = field(default_factory=list)


@dataclass
class Room:
    id: str
    code: str
    title: str
    mode: str
    host_id: str
    minutes_enabled: bool
    created_at: str = field(default_factory=now)
    participants: dict[str, Participant] = field(default_factory=dict)
    presenter_id: str | None = None
    hands: list[str] = field(default_factory=list)
    strokes: list[dict] = field(default_factory=list)
    entries: list[dict] = field(default_factory=list)
    epoch: int = 0
    active: bool = True

    def host_only(self, pid: str):
        if pid != self.host_id:
            raise RuleError("방장만 사용할 수 있는 기능입니다.")

    def can_speak(self, pid: str) -> bool:
        p = self.participants.get(pid)
        return bool(p and p.connected and p.mic and
                    (self.mode == "free" or self.presenter_id == pid))

    def can_present(self, pid: str) -> bool:
        return self.presenter_id == pid

    def set_presenter(self, actor: str, target: str | None):
        self.host_only(actor)
        if target is not None and (target not in self.participants or
                                   not self.participants[target].connected):
            raise RuleError("접속 중인 참석자를 선택하세요.")
        for p in self.participants.values():
            if p.id != target:
                p.sharing = False
        self.presenter_id = target
        self.hands = [p for p in self.hands if p != target]
        self.epoch += 1

    def set_minutes(self, actor: str, enabled: bool, available: bool):
        self.host_only(actor)
        if enabled and self.mode != "meeting":
            raise RuleError("자동 회의록은 회의 모드에서만 사용할 수 있습니다.")
        if enabled and not available:
            raise RuleError("서버에 한국어 음성 인식 모델이 준비되지 않았습니다.")
        self.minutes_enabled = enabled
        self.epoch += 1

    def snapshot(self) -> dict:
        return {
            "id": self.id, "code": self.code, "title": self.title,
            "mode": self.mode, "host_id": self.host_id,
            "presenter_id": self.presenter_id, "minutes_enabled": self.minutes_enabled,
            "created_at": self.created_at, "hands": self.hands,
            "participants": [{"id": p.id, "name": p.name, "mic": p.mic,
                              "camera": p.camera, "sharing": p.sharing,
                              "ready": p.ready, "can_speak": self.can_speak(p.id)}
                             for p in self.participants.values() if p.connected],
        }


class Store:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS rooms (
                id TEXT PRIMARY KEY, title TEXT, code TEXT, mode TEXT,
                created_at TEXT, closed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT, room_id TEXT,
                speaker_id TEXT, speaker TEXT, text TEXT, kind TEXT, at TEXT
            );
            CREATE INDEX IF NOT EXISTS entries_room ON entries(room_id, id);
        """)
        # Live media sessions cannot survive a server restart.
        self.db.execute("UPDATE rooms SET closed_at=? WHERE closed_at IS NULL", (now(),))
        self.db.commit()

    def add_room(self, room: Room):
        self.db.execute("INSERT INTO rooms VALUES (?,?,?,?,?,NULL)",
                        (room.id, room.title, room.code, room.mode, room.created_at))
        self.db.commit()

    def close_room(self, rid: str):
        self.db.execute("UPDATE rooms SET closed_at=? WHERE id=?", (now(), rid))
        self.db.commit()

    def add_entry(self, room: Room, pid: str, speaker: str, text: str, kind="speech", at=None) -> dict:
        entry = {"room_id": room.id, "speaker_id": pid, "speaker": speaker,
                 "text": text, "kind": kind, "at": at or now()}
        cur = self.db.execute(
            "INSERT INTO entries(room_id,speaker_id,speaker,text,kind,at) VALUES (?,?,?,?,?,?)",
            tuple(entry.values()))
        self.db.commit()
        entry["id"] = cur.lastrowid
        room.entries.append(entry)
        room.entries[:] = room.entries[-200:]
        return entry

    def entries(self, rid: str) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM entries WHERE room_id=? ORDER BY at, id", (rid,))]


def minutes_markdown(room: Room, entries: list[dict]) -> str:
    """Extractive organization; never invent agreements or assigned work."""
    def clean(value: str) -> str:
        return value.replace("\r", " ").replace("\n", " ").replace("<", "&lt;").replace(">", "&gt;")

    lines = [f"# {clean(room.title)} — 회의록", "", f"- 시작: {room.created_at} (UTC)",
             f"- 내보내기: {now()} (UTC)", "- 작성 방식: 한국어 음성 인식 + 발언별 분류",
             "- 자동 전사는 오인식될 수 있습니다. 결정·할 일 후보는 검토 후 확정하세요.", "",
             "## 참석 발언자", ""]
    speakers = list(dict.fromkeys(e["speaker"] for e in entries))
    lines += [f"- {clean(s)}" for s in speakers] or ["- 기록된 발언 없음"]
    lines += ["", "## 주요 논의 (발언자별)", ""]
    for speaker in speakers:
        lines += [f"### {clean(speaker)}", ""]
        lines += [f"- {clean(e['text'])}" for e in entries if e["speaker"] == speaker and e["kind"] == "speech"] or ["- 수동 기록만 있음"]
        lines.append("")
    for title, kind in [("확정 결정 (방장 기록)", "decision"), ("실행 항목 (방장 기록)", "action"), ("추가 메모", "note")]:
        lines += [f"## {title}", ""]
        lines += [f"- {clean(e['text'])} — {clean(e['speaker'])}" for e in entries if e["kind"] == kind] or ["- 없음"]
        lines.append("")
    candidates = [e for e in entries if e["kind"] == "speech" and any(
        w in e["text"] for w in ("결정", "합의", "하기로", "담당", "까지", "진행하", "검토하"))]
    lines += ["## 결정·실행 후보 (자동 분류 · 미확정)", ""]
    lines += [f"- {clean(e['text'])} — {clean(e['speaker'])}" for e in candidates] or ["- 없음"]
    lines += ["", "## 시간순 원문", ""]
    lines += [f"- [{e['at']}] **{clean(e['speaker'])}** ({e['kind']}): {clean(e['text'])}" for e in entries] or ["- 기록 없음"]
    return "\n".join(lines) + "\n"
