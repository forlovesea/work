from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from typing import Literal

from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRelay
from aiortc.mediastreams import MediaStreamError
from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .domain import Participant, Room, RuleError, Store
from .media import AudioGate, SpeechService
from .minutes_export import export_minutes
from .approvals import ApprovalService, MASTER_EMAIL

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent


class CreateRoom(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=40)
    mode: str = "meeting"
    minutes_enabled: bool = False
    contact: str = Field(default="", max_length=120)
    approval_id: str = Field(default="", max_length=100)
    approval_token: str = Field(default="", max_length=200)


class ApprovalRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    contact: str = Field(min_length=1, max_length=120)


class ApprovalDecision(BaseModel):
    decision: Literal["approve", "reject"]


class JoinRoom(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=40)


class Hub:
    def __init__(self, store, speech):
        self.store, self.speech = store, speech
        self.rooms: dict[str, Room] = {}
        self.tokens: dict[str, tuple[Room, Participant]] = {}
        self.relay = MediaRelay()
        self.ice = json.loads(os.getenv("ICE_SERVERS_JSON", "[]"))
        self.max_people = int(os.getenv("MAX_PARTICIPANTS", "8"))
        self.max_rooms = int(os.getenv("MAX_ROOMS", "30"))

    def rtc_config(self):
        return RTCConfiguration(iceServers=[RTCIceServer(**server) for server in self.ice])

    def session(self, token):
        found = self.tokens.get(token)
        if not found or not found[0].active:
            raise RuleError("접속 정보가 만료되었습니다. 다시 입장하세요.")
        return found

    def add_person(self, room, name):
        if len(room.participants) >= self.max_people:
            raise RuleError("방의 최대 인원에 도달했습니다.")
        if not name.strip():
            raise RuleError("이름을 입력하세요.")
        p = Participant(secrets.token_hex(8), name.strip())
        p.send_lock = asyncio.Lock()
        room.participants[p.id] = p
        self.tokens[p.token] = (room, p)
        return p

    def credentials(self, room, person):
        return {"room_id": room.id, "code": room.code, "token": person.token,
                "participant_id": person.id, "ice_servers": self.ice}

    async def send(self, p, event):
        if p.ws is not None:
            try:
                async with p.send_lock:
                    await asyncio.wait_for(p.ws.send_json(event), timeout=3)
            except (RuntimeError, WebSocketDisconnect, OSError, asyncio.TimeoutError):
                pass

    async def broadcast(self, room, event):
        await asyncio.gather(*(self.send(p, event) for p in list(room.participants.values())))

    async def state(self, room):
        await self.broadcast(room, {"type": "state", "room": room.snapshot()})

    async def speech_status(self, room, pending):
        await self.broadcast(room, {"type": "speech_status", "pending": pending})

    async def transcript(self, room, p, text, error=None, at=None):
        if error:
            await self.broadcast(room, {"type": "notice", "message": error})
        elif text:
            entry = self.store.add_entry(room, p.id, p.name, text, at=at)
            await self.broadcast(room, {"type": "entry", "entry": entry})

    async def drain(self, track):
        try:
            while True:
                await track.recv()
        except (MediaStreamError, asyncio.CancelledError):
            pass
        finally:
            track.stop()

    async def publish(self, room, p, sdp):
        if p.publisher:
            raise RuleError("이미 미디어가 연결되어 있습니다. 다시 입장하세요.")
        pc = RTCPeerConnection(self.rtc_config())
        p.publisher = pc

        @pc.on("track")
        def track_received(track):
            if track.kind in p.tracks:
                track.stop()
                return
            source = AudioGate(track, lambda: room.can_speak(p.id)) if track.kind == "audio" else track
            p.tracks[track.kind] = source
            consumer = self.relay.subscribe(source, buffered=False)
            coro = self.speech.transcribe(consumer, room, p, self.transcript) if (
                track.kind == "audio" and self.speech.available) else self.drain(consumer)
            p.tasks.append(asyncio.create_task(coro))

        @pc.on("connectionstatechange")
        async def connection_changed():
            if pc.connectionState == "failed":
                p.ready = False
                await self.send(p, {"type": "notice", "message": "미디어 연결이 끊어졌습니다. 나간 뒤 다시 입장하세요."})
                await self.state(room)

        try:
            await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type="offer"))
            await pc.setLocalDescription(await pc.createAnswer())
            p.ready = True
            await self.state(room)
            return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        except Exception:
            await pc.close()
            p.publisher = None
            raise

    async def subscribe(self, room, p, target_id, sdp):
        target = room.participants.get(target_id)
        if not target or not target.ready or target.id == p.id:
            raise RuleError("상대방의 미디어가 아직 준비되지 않았습니다.")
        old = p.subscriptions.pop(target_id, None)
        if old:
            await old.close()
        pc = RTCPeerConnection(self.rtc_config())
        p.subscriptions[target_id] = pc
        try:
            await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type="offer"))
            for source in target.tracks.values():
                pc.addTrack(self.relay.subscribe(source, buffered=False))
            await pc.setLocalDescription(await pc.createAnswer())
            return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        except Exception:
            p.subscriptions.pop(target_id, None)
            await pc.close()
            raise

    async def remove(self, room, p):
        if p.id not in room.participants:
            return
        p.connected = False
        p.mic = False
        p.ready = False
        room.epoch += 1
        self.tokens.pop(p.token, None)
        room.participants.pop(p.id, None)
        room.hands = [pid for pid in room.hands if pid != p.id]
        connected = [x.id for x in room.participants.values() if x.connected]
        if room.host_id == p.id:
            room.host_id = (connected or list(room.participants) or [""])[0]
        if room.presenter_id == p.id:
            room.presenter_id = room.host_id if room.host_id in connected else None
        for task in p.tasks:
            task.cancel()
        await asyncio.gather(*p.tasks, return_exceptions=True)
        pcs = list(p.subscriptions.values())
        if p.publisher:
            pcs.append(p.publisher)
        for other in room.participants.values():
            pc = other.subscriptions.pop(p.id, None)
            if pc:
                pcs.append(pc)
        await asyncio.gather(*(pc.close() for pc in pcs), return_exceptions=True)
        for track in p.tracks.values():
            track.stop()
        if not room.participants:
            room.active = False
            self.rooms.pop(room.id, None)
            self.store.close_room(room.id)
        else:
            await self.state(room)

    async def reap(self):
        while True:
            await asyncio.sleep(15)
            for room in list(self.rooms.values()):
                for p in list(room.participants.values()):
                    if not p.connected and time.monotonic() - p.created > 120:
                        await self.remove(room, p)

    async def command(self, room, p, data):
        action = data.get("action")
        if action in ("publish", "subscribe"):
            sdp = data.get("sdp")
            if not isinstance(sdp, str) or len(sdp) > 80000:
                raise RuleError("올바르지 않은 미디어 연결 요청입니다.")
            if action == "publish":
                return await self.publish(room, p, sdp)
            return await self.subscribe(room, p, data.get("target"), sdp)
        if action == "devices":
            for key in ("mic", "camera"):
                if key in data:
                    if type(data[key]) is not bool:
                        raise RuleError("장치 설정이 올바르지 않습니다.")
                    setattr(p, key, data[key])
            room.epoch += 1
        elif action == "hand":
            if p.id in room.hands:
                room.hands.remove(p.id)
            else:
                room.hands.append(p.id)
        elif action == "presenter":
            room.set_presenter(p.id, data.get("target"))
        elif action == "minutes":
            if type(data.get("enabled")) is not bool:
                raise RuleError("회의록 설정이 올바르지 않습니다.")
            room.set_minutes(p.id, data["enabled"], self.speech.available)
        elif action == "sharing":
            if not room.can_present(p.id):
                raise RuleError("발표자만 화면을 공유할 수 있습니다.")
            if type(data.get("enabled")) is not bool:
                raise RuleError("화면 공유 설정이 올바르지 않습니다.")
            p.sharing = data["enabled"]
        elif action == "stroke":
            if not room.can_present(p.id):
                raise RuleError("발표자만 화이트보드에 그릴 수 있습니다.")
            points = data.get("points")
            color = data.get("color", "#3859ed")
            width = data.get("width", 3)
            if (not isinstance(points, list) or not 1 <= len(points) <= 128 or
                not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color) or
                type(width) not in (int, float) or not 1 <= width <= 16 or
                any(not isinstance(pt, list) or len(pt) != 2 or any(
                    type(x) not in (int, float) or not 0 <= x <= 1 for x in pt) for pt in points)):
                raise RuleError("올바르지 않은 그림 데이터입니다.")
            if len(room.strokes) >= 10000:
                raise RuleError("화이트보드가 가득 찼습니다. 지우고 다시 사용하세요.")
            stroke = {"points": points, "color": color, "width": width}
            room.strokes.append(stroke)
            await self.broadcast(room, {"type": "stroke", "stroke": stroke, "author": p.id})
            return {}
        elif action == "clear_board":
            if not room.can_present(p.id):
                raise RuleError("발표자만 화이트보드를 지울 수 있습니다.")
            room.strokes.clear()
            await self.broadcast(room, {"type": "board", "strokes": []})
            return {}
        elif action == "note":
            room.host_only(p.id)
            text, kind = data.get("text", ""), data.get("kind", "note")
            if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000 or kind not in ("note", "decision", "action"):
                raise RuleError("메모 종류와 내용(최대 2,000자)을 확인하세요.")
            entry = self.store.add_entry(room, p.id, p.name, text.strip(), kind)
            await self.broadcast(room, {"type": "entry", "entry": entry})
            return {}
        elif action == "ping":
            return {}
        else:
            raise RuleError("지원하지 않는 요청입니다.")
        await self.state(room)
        return {}


def create_app(db_path=None, speech=None, *, approval_required=True, approval_sender=None):
    @asynccontextmanager
    async def lifespan(app):
        store = Store(db_path or os.getenv("DB_PATH", str(ROOT / "data" / "meetings.db")))
        if speech is not None:
            recognizer = speech
        elif os.getenv("SPEECH_ENGINE", "vosk") == "whisper":
            from .whisper_speech import WhisperSpeechService
            recognizer = await asyncio.to_thread(WhisperSpeechService, os.getenv("WHISPER_MODEL_PATH", str(ROOT / "models" / "faster-whisper-small")))
        else:
            recognizer = await asyncio.to_thread(SpeechService, os.getenv("VOSK_MODEL_PATH", str(ROOT / "models" / "vosk-model-small-ko-0.22")))
        hub = Hub(store, recognizer)
        if hasattr(recognizer, "on_status"):
            recognizer.on_status = hub.speech_status
        app.state.hub = hub
        app.state.export_slots = asyncio.Semaphore(2)
        app.state.approvals = ApprovalService(store.db, required=approval_required, sender=approval_sender)
        reaper = asyncio.create_task(hub.reap())
        yield
        reaper.cancel()
        await asyncio.gather(reaper, return_exceptions=True)
        for room in list(hub.rooms.values()):
            for p in list(room.participants.values()):
                await hub.remove(room, p)
        if hasattr(recognizer, "close"):
            await recognizer.close()
        store.db.close()

    app = FastAPI(title="모아 화상회의", lifespan=lifespan)
    origins = [s.strip().rstrip("/") for s in os.getenv("ALLOWED_ORIGINS", "").split(",") if s.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])

    @app.get("/api/config")
    async def config():
        h = app.state.hub
        return {"speech_available": h.speech.available, "speech_message": h.speech.error,
                "speech_engine": h.speech.engine,
                "master_approval_required": app.state.approvals.required,
                "master_email_ready": app.state.approvals.ready, "master_email": MASTER_EMAIL,
                "max_participants": h.max_people, "version": "0.1.0"}

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    @app.post("/api/host-approvals", status_code=202)
    async def request_approval(data: ApprovalRequest, request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        return await app.state.approvals.request(data.name, data.contact, request.client.host if request.client else "unknown")

    @app.get("/api/host-approvals/{rid}")
    async def approval_status(rid: str, response: Response, authorization: str = Header(default="")):
        response.headers["Cache-Control"] = "no-store"
        return app.state.approvals.status(rid, authorization.removeprefix("Bearer "))

    @app.get("/api/master-approvals/{rid}")
    async def master_details(rid: str, response: Response, authorization: str = Header(default="")):
        response.headers["Cache-Control"] = "no-store"
        return app.state.approvals.status(rid, authorization.removeprefix("Bearer "), master=True)

    @app.post("/api/master-approvals/{rid}/decision")
    async def master_decision(rid: str, data: ApprovalDecision, response: Response, authorization: str = Header(default="")):
        response.headers["Cache-Control"] = "no-store"
        return app.state.approvals.decide(rid, authorization.removeprefix("Bearer "), data.decision)

    @app.get("/master-approval")
    async def master_page():
        return FileResponse(ROOT / "static" / "master-approval.html", headers={
            "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'"})

    @app.post("/api/rooms", status_code=201)
    async def create(data: CreateRoom):
        h = app.state.hub
        if len(h.rooms) >= h.max_rooms:
            raise HTTPException(503, "현재 생성 가능한 방 수를 초과했습니다.")
        if data.mode not in ("free", "meeting") or not data.title.strip() or not data.name.strip():
            raise HTTPException(422, "방 이름, 참석자 이름, 회의 모드를 확인하세요.")
        if data.minutes_enabled and (data.mode != "meeting" or not h.speech.available):
            raise HTTPException(422, "자동 회의록에는 회의 모드와 설치된 음성 인식 모델이 필요합니다.")
        code = secrets.token_hex(6).upper()
        while any(r.code == code for r in h.rooms.values()):
            code = secrets.token_hex(6).upper()
        room = Room(secrets.token_hex(16), code, data.title.strip(), data.mode, "", data.minutes_enabled)
        app.state.approvals.consume(data.approval_id, data.approval_token, data.name, data.contact)
        p = h.add_person(room, data.name)
        room.host_id = room.presenter_id = p.id
        try:
            h.store.add_room(room)
        except Exception:
            h.store.db.rollback()
            h.tokens.pop(p.token, None)
            raise
        h.rooms[room.id] = room
        return h.credentials(room, p)

    @app.post("/api/join")
    async def join(data: JoinRoom):
        h = app.state.hub
        code = re.sub(r"[\s-]", "", data.code).upper()
        room = next((r for r in h.rooms.values() if r.code == code and r.active), None)
        if room is None:
            raise HTTPException(404, "접속 ID를 확인하세요. 종료된 방에는 입장할 수 없습니다.")
        try:
            return h.credentials(room, h.add_person(room, data.name))
        except RuleError as e:
            raise HTTPException(409, str(e)) from e

    @app.get("/api/rooms/{rid}/minutes")
    async def download(rid: str, authorization: str = Header(default=""),
                       format: Literal["docx", "pdf", "txt"] = "txt", summary: bool = False):
        h = app.state.hub
        try:
            room, _ = h.session(authorization.removeprefix("Bearer "))
            if room.id != rid:
                raise RuleError("다른 방의 회의록에는 접근할 수 없습니다.")
            if hasattr(h.speech, "outstanding") and h.speech.outstanding(room):
                raise HTTPException(409, "음성 인식이 아직 처리 중입니다. 자동 기록을 끄고 대기가 0건이 된 뒤 저장하세요.")
        except RuleError as e:
            raise HTTPException(403, str(e)) from e
        async with app.state.export_slots:
            entries = h.store.entries(rid)
            content, media_type = await asyncio.to_thread(export_minutes, room.title, room.created_at, entries, format, summary)
        return Response(content, media_type=media_type,
                        headers={"Content-Disposition": f'attachment; filename="meeting-minutes.{format}"',
                                 "Cache-Control": "no-store"})

    @app.websocket("/ws")
    async def websocket(ws: WebSocket):
        origin = ws.headers.get("origin")
        if origin and origin not in origins and urlsplit(origin).netloc != ws.headers.get("host"):
            await ws.close(code=1008)
            return
        await ws.accept()
        h = app.state.hub
        room = p = None
        owned = False
        try:
            auth = await asyncio.wait_for(ws.receive_json(), timeout=10)
            room, p = h.session(auth.get("token", ""))
            if p.connected:
                raise RuleError("이미 사용 중인 접속 정보입니다.")
            p.connected, p.ws, owned = True, ws, True
            await h.send(p, {"type": "welcome", "you": p.id, "room": room.snapshot(),
                             "strokes": room.strokes, "entries": room.entries,
                             "speech_pending": h.speech.outstanding(room) if hasattr(h.speech, "outstanding") else 0})
            await h.state(room)
            # Per-socket sliding window; board updates are batched by the client.
            window, count = time.monotonic(), 0
            while True:
                raw = await ws.receive_text()
                if len(raw) > 100000:
                    raise RuleError("요청이 너무 큽니다.")
                if time.monotonic() - window >= 1:
                    window, count = time.monotonic(), 0
                count += 1
                if count > 80:
                    raise RuleError("요청이 너무 빠릅니다.")
                request_id = None
                try:
                    data = json.loads(raw)
                    if not isinstance(data, dict):
                        raise RuleError("올바르지 않은 요청입니다.")
                    request_id = data.get("id")
                    result = await asyncio.wait_for(h.command(room, p, data), timeout=45)
                    await h.send(p, {"type": "reply", "id": request_id, "ok": True, "result": result})
                except (RuleError, ValueError, TypeError, KeyError) as e:
                    await h.send(p, {"type": "reply", "id": request_id, "ok": False, "error": str(e)})
                except Exception:
                    log.exception("Command failed")
                    await h.send(p, {"type": "reply", "id": request_id, "ok": False,
                                     "error": "서버에서 요청을 처리하지 못했습니다. 연결 설정을 확인하고 다시 입장하세요."})
        except (WebSocketDisconnect, asyncio.TimeoutError):
            pass
        except (RuleError, ValueError, TypeError, AttributeError):
            await ws.close(code=1008)
        finally:
            if owned:
                p.ws = None
                await h.remove(room, p)

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    @app.get("/")
    async def index():
        return FileResponse(ROOT / "static" / "index.html")

    return app


app = create_app()
