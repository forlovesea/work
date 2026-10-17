import asyncio
import json
import time
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from app.main import create_app, Hub
from app.domain import Room, Store
from app.media import SpeechService
from app.master_auth import write_key
from test_rooms import connect, command, until

TEST_KEY = "test-only-master-password-2026"


def test_empty_room_cannot_be_rejoined_during_media_cleanup():
    async def scenario():
        store = Store(":memory:")
        hub = Hub(store, SpeechService(""))
        room = Room("r", "CODE", "Cleanup", "meeting", "", False)
        hub.rooms[room.id] = room
        person = hub.add_person(room, "Host")
        started, finish = asyncio.Event(), asyncio.Event()

        class SlowPeer:
            async def close(self):
                started.set()
                await finish.wait()

        person.publisher = SlowPeer()
        task = asyncio.create_task(hub.remove(room, person))
        await asyncio.wait_for(started.wait(), 2)
        try:
            assert not room.active
            assert room.id not in hub.rooms
            assert person.token not in hub.tokens
        finally:
            finish.set()
            await task
            store.db.close()

    asyncio.run(scenario())


@pytest.fixture
def master_client(tmp_path):
    path = tmp_path / "key.json"
    write_key(path, TEST_KEY)
    app = create_app(str(tmp_path / "master.db"), SpeechService(""), master_key_path=path)
    with TestClient(app) as client:
        yield client, path


def login(client, key=TEST_KEY):
    response = client.post("/api/master/login", json={"key": key})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return {"Authorization": "Bearer " + response.json()["token"]}


def create(client, headers):
    result = client.post("/api/rooms", headers=headers, json={"name": "Master", "title": "관리 회의"})
    assert result.status_code == 201, result.text
    return result.json()


def test_only_password_session_can_manage_rooms(master_client):
    client, path = master_client
    assert TEST_KEY not in path.read_text()
    assert client.get("/api/config").json()["master_password_ready"]
    assert client.post("/api/master/login", json={"key": "wrong"}).status_code == 401
    assert client.get("/api/master/rooms").status_code == 401
    assert client.post("/api/rooms", json={"name": "Fake", "title": "Fake", "is_master": True}).status_code == 403
    headers = login(client)
    host = create(client, headers)  # No SMTP or email approval required.
    participant_headers = {"Authorization": "Bearer " + host["token"]}
    rid = host["room_id"]
    for auth in ({}, participant_headers, {"Authorization": "Bearer forlovesea@gmail.com"}):
        assert client.get("/api/master/rooms", headers=auth).status_code == 401
        assert client.post(f"/api/master/rooms/{rid}/delete", headers=auth).status_code == 401
        assert client.post(f"/api/master/rooms/{rid}/participants/{host['participant_id']}/kick", headers=auth).status_code == 401
    rooms = client.get("/api/master/rooms", headers=headers)
    assert rooms.json()["rooms"][0]["participants"][0]["is_master"]
    assert host["token"] not in rooms.text and "hash" not in rooms.text
    assert client.post("/api/master/logout", headers=headers).status_code == 200
    assert client.get("/api/master/rooms", headers=headers).status_code == 401
    assert client.post("/api/rooms", headers=headers, json={"name": "M", "title": "M"}).status_code == 401


def test_kick_revokes_live_session_rotates_invite_and_transfers_host(master_client):
    client, _ = master_client
    headers = login(client)
    host = create(client, headers)
    guest = client.post("/api/join", json={"code": host["code"], "name": "참석자"}).json()
    with connect(client, host) as (host_ws, _), connect(client, guest) as (guest_ws, _):
        assert command(host_ws, "note", kind="note", text="보존할 기록")["ok"]
        result = client.post(f"/api/master/rooms/{host['room_id']}/participants/{host['participant_id']}/kick", headers=headers)
        assert result.status_code == 200
        until(host_ws, "removed")
        with pytest.raises(WebSocketDisconnect):
            host_ws.receive_json()
        room = client.app.state.hub.rooms[host["room_id"]]
        assert room.host_id == guest["participant_id"]
        assert host["token"] not in client.app.state.hub.tokens
        assert room.code != host["code"]
        assert client.post("/api/join", json={"code": host["code"], "name": "재입장"}).status_code == 404
        assert client.get(f"/api/rooms/{room.id}/minutes", headers={"Authorization": "Bearer " + host["token"]}).status_code == 403
        assert command(guest_ws, "note", kind="note", text="새 방장 기록")["ok"]


def test_delete_closes_every_session_and_keeps_stored_minutes(master_client):
    client, _ = master_client
    headers = login(client)
    host = create(client, headers)
    guest = client.post("/api/join", json={"code": host["code"], "name": "참석자"}).json()
    with connect(client, host) as (host_ws, _), connect(client, guest) as (guest_ws, _):
        command(host_ws, "note", kind="note", text="기록은 남긴다")
        assert client.post(f"/api/master/rooms/{host['room_id']}/delete", headers=headers).status_code == 200
        until(host_ws, "removed")
        until(guest_ws, "removed")
        h = client.app.state.hub
        assert host["room_id"] not in h.rooms
        assert host["token"] not in h.tokens and guest["token"] not in h.tokens
        assert h.store.entries(host["room_id"])[0]["text"] == "기록은 남긴다"
        assert client.post("/api/join", json={"code": host["code"], "name": "재입장"}).status_code == 404
        assert client.get("/api/master/rooms", headers=headers).json() == {"rooms": []}
        assert h.store.db.execute("SELECT count(*) FROM master_audit WHERE action='delete_room'").fetchone()[0] == 1


def test_reset_expiry_and_login_rate_limit(master_client):
    client, path = master_client
    headers = login(client)
    write_key(path, "changed-test-master-key-2026")
    assert client.get("/api/master/me", headers=headers).status_code == 401
    new = login(client, "changed-test-master-key-2026")
    auth = client.app.state.master
    auth.sessions[auth.token_hash(new["Authorization"].removeprefix("Bearer "))]["expires_at"] = time.time() - 1
    assert client.get("/api/master/me", headers=new).status_code == 401
    for _ in range(4):
        assert client.post("/api/master/login", json={"key": "wrong"}).status_code == 401
    assert client.post("/api/master/login", json={"key": "wrong"}).status_code == 429


def test_master_reserved_slot_and_email_users_remain_restricted(master_client):
    client, _ = master_client
    headers = login(client)
    host = create(client, headers)
    client.app.state.hub.max_people = 1
    assert client.post("/api/join", json={"name": "일반", "code": host["code"]}).status_code == 409
    result = client.post("/api/join", headers=headers, json={"name": "관리자", "code": host["code"]})
    assert result.status_code == 200
    assert client.post("/api/join", headers=headers, json={"name": "추가 관리자", "code": host["code"]}).status_code == 409


def test_missing_key_fails_closed(tmp_path):
    with TestClient(create_app(str(tmp_path / "missing.db"), SpeechService(""), master_key_path=tmp_path / "absent.json")) as client:
        assert not client.get("/api/config").json()["master_password_ready"]
        assert client.post("/api/master/login", json={"key": TEST_KEY}).status_code == 503
