import json
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from test_phase4 import Clock, AUTH, TOKEN, package, upload
from app.main import create_app


@pytest.fixture
def server(tmp_path):
    clock = Clock()
    app = create_app(tmp_path / "mobile.db", TOKEN, clock=clock)
    with TestClient(app) as client:
        yield client, app, clock


def pair(client):
    response = client.post("/api/v1/pairing/codes", headers=AUTH)
    assert response.status_code == 200
    code = response.json()["code"]
    response = client.post("/api/v1/pairing/claim", json={"code": code, "device_name": "Android Mock"})
    assert response.status_code == 200
    return response.json(), code


def test_pairing_one_use_read_only_and_revocation(server, package):
    client, app, clock = server
    assert client.post("/api/v1/pairing/codes").status_code == 401
    device, code = pair(client)
    headers = {"X-Device-Token": device["token"]}
    assert client.post("/api/v1/pairing/claim", json={"code": code, "device_name": "again"}).status_code == 401
    assert client.get("/api/v1/events", headers=headers).status_code == 200
    assert client.get("/api/v1/packages", headers=headers).status_code == 200
    assert client.post("/api/v1/events", json={}, headers=headers).status_code == 401
    assert client.post("/api/v1/packages", headers=headers).status_code == 401
    assert client.post("/api/v1/pairing/codes", headers=headers).status_code == 401
    result = upload(client, package).json()
    assert client.get(f'/api/v1/packages/{result["package_id"]}/download', headers=headers).content == package
    with closing(app.state.mobile.connect()) as db:
        saved = dict(db.execute("SELECT * FROM mobile_devices").fetchone())
        assert saved["token_hash"] != device["token"]
        assert device["token"] not in json.dumps(saved)
    assert "token_hash" not in client.get("/api/v1/devices", headers=AUTH).text
    assert client.delete(f'/api/v1/devices/{device["device_id"]}', headers=AUTH).status_code == 200
    assert client.get("/api/v1/events", headers=headers).status_code == 401


def test_pairing_expiry_and_concurrent_claim(server):
    client, app, clock = server
    code = client.post("/api/v1/pairing/codes", headers=AUTH).json()["code"]
    clock.now += timedelta(minutes=10)
    assert client.post("/api/v1/pairing/claim", json={"code": code, "device_name": "expired"}).status_code == 401
    code = client.post("/api/v1/pairing/codes", headers=AUTH).json()["code"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post("/api/v1/pairing/claim", json={"code": code, "device_name": "race"}), range(4)))
    assert sorted(r.status_code for r in results) == [200, 401, 401, 401]
    token = next(r.json()["token"] for r in results if r.status_code == 200)
    clock.now += timedelta(days=90)
    assert client.get("/api/v1/events", headers={"X-Device-Token": token}).status_code == 401


def post_event(client):
    event = {"event_id": str(uuid.uuid4()), "device_id": "PC", "event_type": "PUBLISH_FAILED"}
    assert client.post("/api/v1/events", headers=AUTH, json=event).status_code == 200
    return event


def test_websocket_auth_replay_live_and_revoke(server):
    client, _, _ = server
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/v1/events/ws"):
            pass
    device, _ = pair(client)
    headers = {"X-Device-Token": device["token"]}
    first = post_event(client)
    with client.websocket_connect("/api/v1/events/ws?after=0", headers=headers) as ws:
        frame = ws.receive_json()
        assert frame["events"][0]["event_id"] == first["event_id"]
        cursor = frame["cursor"]
        assert ws.receive_json()["type"] == "heartbeat"
        second = post_event(client)
        ws.send_text("sync")
        frame = ws.receive_json()
        assert frame["events"][0]["event_id"] == second["event_id"]
    with client.websocket_connect(f"/api/v1/events/ws?after={cursor}", headers=headers) as ws:
        assert ws.receive_json()["events"][0]["event_id"] == second["event_id"]
        client.delete(f'/api/v1/devices/{device["device_id"]}', headers=AUTH)
        ws.send_text("check-revoke")
        with pytest.raises(WebSocketDisconnect) as caught:
            while True:
                ws.receive_json()
        assert caught.value.code == 4401


def test_fcm_registration_delivery_retry_and_disabled_mode(server):
    client, app, _ = server
    device, _ = pair(client)
    headers = {"X-Device-Token": device["token"]}
    assert client.put("/api/v1/devices/me/push", headers=AUTH, json={"token": "mock"}).status_code == 401
    response = client.put("/api/v1/devices/me/push", headers=headers, json={"token": "fake-fcm-token"})
    assert response.json() == {"registered": True, "delivery_enabled": False}
    calls = []
    def fail(token, data):
        raise RuntimeError("mock offline")
    app.state.mobile.push_sender = fail
    event = post_event(client)
    app.state.mobile.dispatch_push()
    with closing(app.state.mobile.connect()) as db:
        assert db.execute("SELECT fcm_cursor FROM mobile_devices").fetchone()[0] == 0
    app.state.mobile.push_sender = lambda token, data: calls.append((token, data))
    app.state.mobile.dispatch_push()
    app.state.mobile.dispatch_push()
    assert len(calls) == 1
    assert calls[0][1]["event_id"] == event["event_id"]
    assert set(calls[0][1]) == {"event_id", "event_type", "sequence"}
    client.put("/api/v1/devices/me/push", headers=headers, json={"token": "rotated-token"})
    app.state.mobile.dispatch_push()
    assert len(calls) == 1
    client.delete(f'/api/v1/devices/{device["device_id"]}', headers=AUTH)
    post_event(client)
    app.state.mobile.dispatch_push()
    assert len(calls) == 1
