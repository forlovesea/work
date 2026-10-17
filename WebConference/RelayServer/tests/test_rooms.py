from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.media import SpeechService


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(str(tmp_path / "test.db"), SpeechService(""), approval_required=False)) as client:
        yield client


def create(client, **extra):
    response = client.post("/api/rooms", json={"title": "팀 회의", "name": "방장", **extra})
    assert response.status_code == 201, response.text
    return response.json()


def join(client, code, name="참석자"):
    return client.post("/api/join", json={"code": code, "name": name}).json()


def until(ws, event_type):
    for _ in range(30):
        event = ws.receive_json()
        if event["type"] == event_type:
            return event
    raise AssertionError("Missing event: " + event_type)


@contextmanager
def connect(client, credentials):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"token": credentials["token"]})
        welcome = until(ws, "welcome")
        yield ws, welcome


def command(ws, action, **kwargs):
    ws.send_json({"id": 1, "action": action, **kwargs})
    return until(ws, "reply")


def test_join_defaults_and_secret_not_in_snapshot(client):
    host = create(client)
    assert len(host["code"]) == 12
    with connect(client, host) as (_, welcome):
        guest = join(client, host["code"].lower())
        with connect(client, guest) as (_, state):
            assert len(state["room"]["participants"]) == 2
            assert not state["room"]["participants"][1]["mic"]
            assert not state["room"]["participants"][1]["can_speak"]
            assert "token" not in str(welcome["room"])


def test_single_speaker_and_permissions(client):
    host = create(client)
    with connect(client, host) as (h, _):
        guest = join(client, host["code"])
        with connect(client, guest) as (g, _):
            assert command(h, "devices", mic=True)["ok"]
            assert command(g, "devices", mic=True)["ok"]
            room = client.app.state.hub.rooms[host["room_id"]]
            assert room.can_speak(host["participant_id"])
            assert not room.can_speak(guest["participant_id"])
            assert not command(g, "presenter", target=guest["participant_id"])["ok"]
            assert command(g, "hand")["ok"]
            assert guest["participant_id"] in room.hands
            assert command(h, "presenter", target=guest["participant_id"])["ok"]
            assert room.can_speak(guest["participant_id"])
            assert not room.can_speak(host["participant_id"])
            assert guest["participant_id"] not in room.hands
            assert not command(g, "minutes", enabled=True)["ok"]


def test_free_talk_allows_simultaneous_audio(client):
    host = create(client, mode="free")
    with connect(client, host) as (h, _):
        guest = join(client, host["code"])
        with connect(client, guest) as (g, _):
            command(h, "devices", mic=True)
            command(g, "devices", mic=True)
            room = client.app.state.hub.rooms[host["room_id"]]
            assert all(room.can_speak(pid) for pid in room.participants)
            assert not command(h, "minutes", enabled=True)["ok"]


def test_whiteboard_authorization_validation_and_late_join(client):
    host = create(client)
    stroke = {"points": [[0.1, 0.2], [0.8, 0.9]], "color": "#112233", "width": 3}
    with connect(client, host) as (h, _):
        assert command(h, "stroke", **stroke)["ok"]
        guest = join(client, host["code"])
        with connect(client, guest) as (g, welcome):
            assert welcome["strokes"] == [stroke]
            assert not command(g, "stroke", **stroke)["ok"]
            assert not command(g, "clear_board")["ok"]
            assert not command(g, "sharing", enabled=True)["ok"]
            assert not command(h, "stroke", points=[[2, -1]], color="#112233", width=3)["ok"]
            assert command(h, "clear_board")["ok"]
            assert client.app.state.hub.rooms[host["room_id"]].strokes == []


def test_minutes_persistence_export_and_room_isolation(client):
    host = create(client)
    other = create(client)
    with connect(client, host) as (h, _):
        assert command(h, "note", kind="decision", text="시제품을 다음 주에 검토하기로 합의")["ok"]
        guest = join(client, host["code"])
        with connect(client, guest) as (g, welcome):
            assert welcome["entries"][0]["kind"] == "decision"
            assert not command(g, "note", kind="decision", text="위조 결정")["ok"]
            url = f"/api/rooms/{host['room_id']}/minutes"
            assert client.get(url).status_code == 403
            assert client.get(url, headers={"Authorization": "Bearer " + other["token"]}).status_code == 403
            response = client.get(url, headers={"Authorization": "Bearer " + guest["token"]})
            assert response.status_code == 200
            assert "확정 결정" in response.text and "시제품" in response.text
            assert len(client.app.state.hub.store.entries(host["room_id"])) == 1


def test_disconnect_transfers_host_and_closes_empty_room(client):
    host = create(client)
    with client.websocket_connect("/ws") as h:
        h.send_json({"token": host["token"]}); until(h, "welcome")
        guest = join(client, host["code"])
        with connect(client, guest) as (g, _):
            h.close()
            for _ in range(10):
                snapshot = until(g, "state")["room"]
                if snapshot["host_id"] == guest["participant_id"]:
                    break
            assert snapshot["host_id"] == guest["participant_id"]
            assert command(g, "note", text="새 방장 기록")["ok"]
    assert client.post("/api/join", json={"code": host["code"], "name": "늦은 참석"}).status_code == 404


def test_no_model_and_invalid_inputs(client):
    assert not client.get("/api/config").json()["speech_available"]
    assert client.post("/api/rooms", json={"title": "회의", "name": "방장", "minutes_enabled": True}).status_code == 422
    assert client.post("/api/rooms", json={"title": " ", "name": "방장"}).status_code == 422
    assert client.post("/api/join", json={"code": "bad", "name": "참석자"}).status_code == 404
    host = create(client)
    with connect(client, host) as (h, _):
        assert not command(h, "minutes", enabled=True)["ok"]
        assert not command(h, "devices", mic="true")["ok"]


def test_duplicate_session_does_not_evict_original(client):
    host = create(client)
    with connect(client, host) as (h, _):
        with client.websocket_connect("/ws") as duplicate:
            duplicate.send_json({"token": host["token"]})
            assert duplicate.receive()["type"] == "websocket.close"
        assert command(h, "ping")["ok"]


def test_capacity(client):
    client.app.state.hub.max_people = 2
    host = create(client)
    join(client, host["code"])
    response = client.post("/api/join", json={"code": host["code"], "name": "세 번째"})
    assert response.status_code == 409


def test_foreign_websocket_origin_rejected(client):
    with pytest.raises(Exception):
        with client.websocket_connect("/ws", headers={"origin": "https://unrelated.example"}):
            pass
