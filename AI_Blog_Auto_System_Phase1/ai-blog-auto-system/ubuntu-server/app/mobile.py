"""One-use pairing, read-only monitor tokens, resumable WebSocket and optional FCM."""
import asyncio
import hashlib
import json
import logging
import os
import secrets
import uuid
from contextlib import closing
from datetime import timedelta

from fastapi import Depends, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

LOG = logging.getLogger(__name__)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class PairRequest(BaseModel):
    code: str = Field(pattern=r"^[0-9a-f]{32}$")
    device_name: str = Field(min_length=1, max_length=100)


class PushRegistration(BaseModel):
    token: str = Field(min_length=1, max_length=4096)


class MobileService:
    def __init__(self, connect, clock, push_sender=None):
        self.connect, self.clock, self.push_sender = connect, clock, push_sender

    def initialize(self):
        with closing(self.connect()) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS pairing_codes (hash TEXT PRIMARY KEY, expires_at TEXT NOT NULL)")
            db.execute("""CREATE TABLE IF NOT EXISTS mobile_devices (
                device_id TEXT PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT UNIQUE NOT NULL,
                expires_at TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0,
                fcm_token TEXT, fcm_cursor INTEGER NOT NULL DEFAULT 0)""")

    def verify(self, token):
        if not token:
            raise HTTPException(401, "Missing device token")
        self.initialize()
        with closing(self.connect()) as db:
            row = db.execute("SELECT * FROM mobile_devices WHERE token_hash=? AND revoked=0 AND expires_at>?",
                             (digest(token), self.clock().isoformat())).fetchone()
        if not row:
            raise HTTPException(401, "Invalid or expired monitor token")
        return dict(row)

    def issue_code(self):
        self.initialize()
        code = secrets.token_hex(16)
        expires = self.clock() + timedelta(minutes=10)
        with closing(self.connect()) as db, db:
            db.execute("DELETE FROM pairing_codes WHERE expires_at<=?", (self.clock().isoformat(),))
            db.execute("INSERT INTO pairing_codes VALUES (?,?)", (digest(code), expires.isoformat()))
        return {"code": code, "expires_at": expires.isoformat()}

    def pair(self, request):
        self.initialize()
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            result = db.execute("DELETE FROM pairing_codes WHERE hash=? AND expires_at>?",
                                (digest(request.code), self.clock().isoformat()))
            if result.rowcount != 1:
                raise HTTPException(401, "Invalid, used or expired pairing code")
            token = secrets.token_urlsafe(32)
            device_id = str(uuid.uuid4())
            expires = self.clock() + timedelta(days=90)
            db.execute("INSERT INTO mobile_devices(device_id,name,token_hash,expires_at) VALUES (?,?,?,?)",
                       (device_id, request.device_name, digest(token), expires.isoformat()))
        return {"device_id": device_id, "token": token, "expires_at": expires.isoformat()}

    def events(self, after):
        with closing(self.connect()) as db:
            rows = db.execute("SELECT rowid AS sequence,* FROM events WHERE rowid>? ORDER BY rowid LIMIT 100", (after,)).fetchall()
        return [{**dict(r), "payload": json.loads(r["payload"])} for r in rows]

    def register_push(self, device, token):
        with closing(self.connect()) as db, db:
            cursor = db.execute("SELECT COALESCE(MAX(rowid),0) FROM events").fetchone()[0]
            # Preserve cursor on token rotation; first registration starts with new events.
            db.execute("UPDATE mobile_devices SET fcm_cursor=CASE WHEN fcm_token IS NULL THEN ? ELSE fcm_cursor END, "
                       "fcm_token=? WHERE device_id=?", (cursor, token, device["device_id"]))

    def dispatch_push(self):
        if not self.push_sender:
            return
        self.initialize()
        with closing(self.connect()) as db:
            devices = db.execute("SELECT * FROM mobile_devices WHERE revoked=0 AND expires_at>? AND fcm_token IS NOT NULL",
                                 (self.clock().isoformat(),)).fetchall()
        for device in devices:
            for event in self.events(device["fcm_cursor"]):
                try:
                    self.push_sender(device["fcm_token"], {"event_id": event["event_id"],
                                     "event_type": event["event_type"], "sequence": str(event["sequence"])})
                except Exception:
                    LOG.warning("FCM delivery failed; retry pending for device %s", device["device_id"])
                    break
                with closing(self.connect()) as db, db:
                    db.execute("UPDATE mobile_devices SET fcm_cursor=MAX(fcm_cursor,?) WHERE device_id=? AND fcm_token=?",
                               (event["sequence"], device["device_id"], device["fcm_token"]))

    async def push_loop(self, stop):
        while not stop.is_set():
            try:
                await asyncio.to_thread(self.dispatch_push)
            except Exception:
                LOG.warning("FCM worker unavailable; retry pending")
            try:
                await asyncio.wait_for(stop.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass


def firebase_sender():
    credential_path = os.getenv("BLOG_FCM_CREDENTIALS")
    if not credential_path:
        return None
    # Optional server dependency. Never shipped to Android or needed in Mock tests.
    import firebase_admin
    from firebase_admin import credentials, messaging
    firebase = firebase_admin.initialize_app(credentials.Certificate(credential_path), name="blog-" + uuid.uuid4().hex)
    def send(token, data):
        messaging.send(messaging.Message(token=token, data=data,
                       android=messaging.AndroidConfig(priority="high", ttl=timedelta(hours=1))), app=firebase)
    return send


def install_mobile(application, mobile, admin_auth, read_auth):
    @application.post("/api/v1/pairing/codes", dependencies=[Depends(admin_auth)])
    def issue_code():
        return mobile.issue_code()

    @application.post("/api/v1/pairing/claim")
    def pair(request: PairRequest):
        return mobile.pair(request)

    @application.get("/api/v1/devices", dependencies=[Depends(admin_auth)])
    def devices():
        mobile.initialize()
        with closing(mobile.connect()) as db:
            return [dict(r) for r in db.execute("SELECT device_id,name,expires_at,revoked FROM mobile_devices")]

    @application.delete("/api/v1/devices/{device_id}", dependencies=[Depends(admin_auth)])
    def revoke(device_id: uuid.UUID):
        mobile.initialize()
        with closing(mobile.connect()) as db, db:
            db.execute("UPDATE mobile_devices SET revoked=1,fcm_token=NULL WHERE device_id=?", (str(device_id),))
        return {"revoked": True}

    @application.put("/api/v1/devices/me/push")
    def register(request: PushRegistration, x_device_token: str | None = Header(None)):
        mobile.register_push(mobile.verify(x_device_token), request.token)
        return {"registered": True, "delivery_enabled": mobile.push_sender is not None}

    @application.websocket("/api/v1/events/ws")
    async def socket(websocket: WebSocket, after: int = Query(0, ge=0)):
        token = websocket.headers.get("x-device-token")
        try:
            await asyncio.to_thread(read_auth, token)
        except HTTPException:
            await websocket.close(code=4401)
            return
        await websocket.accept()
        try:
            while True:
                try:
                    await asyncio.to_thread(read_auth, token)
                except HTTPException:
                    await websocket.close(code=4401)
                    return
                rows = await asyncio.to_thread(mobile.events, after)
                if rows:
                    after = rows[-1]["sequence"]
                    await websocket.send_json({"type": "events", "events": rows, "cursor": after})
                    continue  # Drain all persisted pages before waiting.
                await websocket.send_json({"type": "heartbeat", "cursor": after})
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=1)
                except asyncio.TimeoutError:
                    pass
        except (WebSocketDisconnect, RuntimeError):
            return
