import importlib.util
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ubuntu-server"))
from app.main import create_app, EVENT_TYPES

spec = importlib.util.spec_from_file_location("sender", ROOT / "windows-app/send_mock_event.py")
sender = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sender)
TOKEN = "test-only-token"
HEADERS = {"X-Device-Token": TOKEN}

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "events.db", TOKEN)) as client:
        yield client


def test_health_auth_and_fail_closed(client, tmp_path):
    assert client.get("/api/v1/health").json()["status"] == "ok"
    for headers in ({}, {"X-Device-Token": "wrong"}):
        assert client.get("/api/v1/events", headers=headers).status_code == 401
        assert client.post("/api/v1/events", headers=headers, json=sender.mock_event("PC")).status_code == 401
    with TestClient(create_app(tmp_path / "closed.db", "")) as closed:
        assert closed.get("/api/v1/events", headers=HEADERS).status_code == 401


def test_duplicate_conflict_persistence(tmp_path):
    path = tmp_path / "events.db"
    event = sender.mock_event("PC")
    with TestClient(create_app(path, TOKEN)) as client:
        assert client.post("/api/v1/events", headers=HEADERS, json=event).json()["new"] is True
        assert client.post("/api/v1/events", headers=HEADERS, json=event).json()["new"] is False
        changed = {**event, "payload": {"different": True}}
        assert client.post("/api/v1/events", headers=HEADERS, json=changed).status_code == 409
    with TestClient(create_app(path, TOKEN)) as restarted:
        rows = restarted.get("/api/v1/events", headers=HEADERS).json()
        assert len(rows) == 1
        assert rows[0]["payload"] == event["payload"]


@pytest.mark.parametrize("changes", [
    {"event_type": "UNKNOWN"}, {"event_id": "bad"}, {"device_id": ""},
    {"occurred_at": "2026-01-01T00:00:00"}, {"extra": True},
    {"payload": {"text": "x" * 17000}},
])
def test_validation(client, changes):
    assert client.post("/api/v1/events", headers=HEADERS,
                       json={**sender.mock_event("PC"), **changes}).status_code == 422


def test_cursor_recovery_and_limits(client):
    for _ in range(3):
        assert client.post("/api/v1/events", headers=HEADERS, json=sender.mock_event("PC")).status_code == 200
    first = client.get("/api/v1/events?after=0&limit=2", headers=HEADERS).json()
    rest = client.get(f"/api/v1/events?after={first[-1]['sequence']}", headers=HEADERS).json()
    assert len(first) == 2 and len(rest) == 1
    assert first[0]["sequence"] < first[1]["sequence"] < rest[0]["sequence"]
    for query in ("limit=0", "limit=101", "after=-1"):
        assert client.get("/api/v1/events?" + query, headers=HEADERS).status_code == 422


def test_concurrent_duplicate(client):
    event = sender.mock_event("PC")
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: client.post("/api/v1/events", headers=HEADERS, json=event), range(8)))
    assert all(r.status_code == 200 for r in responses)
    assert sum(r.json()["new"] for r in responses) == 1


def test_outbox_network_failure_then_replay(client, tmp_path):
    path = tmp_path / "outbox.db"
    box = sender.Outbox(path)
    event = sender.mock_event("PC")
    box.enqueue(event)
    def offline(request):
        raise httpx.ConnectError("offline", request=request)
    with httpx.Client(transport=httpx.MockTransport(offline)) as offline_client:
        with pytest.raises(httpx.ConnectError):
            box.flush(offline_client, "http://localhost", TOKEN)
    # Simulate server commit followed by lost response, then restart the sender.
    client.post("/api/v1/events", headers=HEADERS, json=event)
    restarted = sender.Outbox(path)
    assert restarted.flush(client, "http://testserver", TOKEN) == 1
    assert restarted.flush(client, "http://testserver", TOKEN) == 0
    assert len(client.get("/api/v1/events", headers=HEADERS).json()) == 1


def test_outbox_auth_failure_preserves_event(client, tmp_path):
    box = sender.Outbox(tmp_path / "outbox.db")
    box.enqueue(sender.mock_event("PC"))
    with pytest.raises(httpx.HTTPStatusError):
        box.flush(client, "http://testserver", "wrong")
    assert box.flush(client, "http://testserver", TOKEN) == 1


@pytest.mark.parametrize("url", ["http://example.com", "http://localhost:8000@evil.com", "https://a.com?secret=x", "ftp://localhost"])
def test_remote_plaintext_rejected(url):
    with pytest.raises(ValueError):
        sender.validate_url(url)


def test_contract():
    schema = json.loads((ROOT / "shared/event-schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    validator.validate(sender.mock_event("PC"))
    validator.validate(json.loads((ROOT / "shared/event-schema.example.json").read_text(encoding="utf-8")))
    assert set(schema["properties"]["event_type"]["enum"]) == EVENT_TYPES
