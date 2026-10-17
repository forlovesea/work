import time
from urllib.parse import urlsplit, parse_qs
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.media import SpeechService
from app.approvals import MASTER_EMAIL


@pytest.fixture
def approval_client(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://61.105.141.21:10443")
    sent = []
    app = create_app(str(tmp_path / "approval.db"), SpeechService(""),
                     approval_sender=lambda name, contact, link: sent.append((name, contact, link)))
    with TestClient(app) as client:
        yield client, sent


def request(client, sent, contact="host@example.com", name="지현"):
    response = client.post("/api/host-approvals", json={"name": name, "contact": contact})
    assert response.status_code == 202, response.text
    data = response.json()
    master = parse_qs(urlsplit(sent[-1][2]).fragment)["token"][0]
    assert master not in response.text
    return data, master


def auth(token):
    return {"Authorization": "Bearer " + token}


def room_body(data, **extra):
    return {"title": "승인 회의", "name": "지현", "contact": "host@example.com",
            "approval_id": data["request_id"], "approval_token": data["client_token"], **extra}


def test_default_denies_creation_without_master_and_separates_tokens(approval_client):
    client, sent = approval_client
    assert client.get("/api/config").json()["master_approval_required"]
    assert client.post("/api/rooms", json={"title": "회의", "name": "방장", "approval_required": False}).status_code == 403
    data, master = request(client, sent)
    rid = data["request_id"]
    assert sent[0][:2] == ("지현", "host@example.com")
    assert client.post("/api/rooms", json=room_body(data)).status_code == 403
    assert client.get(f"/api/master-approvals/{rid}", headers=auth(data["client_token"])).status_code == 403
    assert client.get(f"/api/host-approvals/{rid}", headers=auth(master)).status_code == 403
    assert client.get(f"/api/master-approvals/{rid}").status_code == 403
    details = client.get(f"/api/master-approvals/{rid}", headers=auth(master))
    assert details.json()["name"] == "지현" and details.json()["status"] == "pending"
    assert details.headers["cache-control"] == "no-store"
    assert client.post("/api/rooms", json=room_body(data)).status_code == 403  # GET never approves.
    decision = f"/api/master-approvals/{rid}/decision"
    assert client.post(decision, headers=auth(data["client_token"]), json={"decision": "approve"}).status_code == 403
    assert client.post(decision, headers=auth(master), json={"decision": "approve"}).status_code == 200
    assert client.post("/api/rooms", json=room_body(data, name="다른 사람")).status_code == 403
    assert client.post("/api/rooms", json=room_body(data, contact="other@example.com")).status_code == 403
    room = client.post("/api/rooms", json=room_body(data))
    assert room.status_code == 201
    assert client.post("/api/rooms", json=room_body(data)).status_code == 403
    assert client.post(decision, headers=auth(master), json={"decision": "approve"}).status_code == 409
    assert client.post("/api/join", json={"code": room.json()["code"], "name": "참석자"}).status_code == 200


def test_rejection_expiry_and_rate_limits(approval_client):
    client, sent = approval_client
    data, master = request(client, sent)
    rid = data["request_id"]
    path = f"/api/master-approvals/{rid}/decision"
    assert client.post(path, headers=auth(master), json={"decision": "reject"}).json()["status"] == "rejected"
    assert client.post(path, headers=auth(master), json={"decision": "approve"}).status_code == 409
    assert client.post("/api/rooms", json=room_body(data)).status_code == 403
    assert client.post("/api/host-approvals", json={"name": "지현", "contact": "host@example.com"}).status_code == 429
    data, master = request(client, sent, "another@example.com")
    rid = data["request_id"]
    client.app.state.hub.store.db.execute("UPDATE host_approvals SET expires=? WHERE id=?", (time.time() - 1, rid))
    client.app.state.hub.store.db.commit()
    assert client.get(f"/api/host-approvals/{rid}", headers=auth(data["client_token"])).json()["status"] == "expired"
    assert client.post(f"/api/master-approvals/{rid}/decision", headers=auth(master), json={"decision": "approve"}).status_code == 410


def test_mail_failure_and_invalid_contacts_fail_closed(approval_client):
    client, sent = approval_client
    def fail(*args):
        raise OSError("mail unavailable")
    client.app.state.approvals.sender = fail
    assert client.post("/api/host-approvals", json={"name": "방장", "contact": "host@example.com"}).status_code == 503
    assert not sent
    for name, contact in [(" ", "host@example.com"), ("방장", "unknown"), ("방장\n주입", "01012345678")]:
        assert client.post("/api/host-approvals", json={"name": name, "contact": contact}).status_code == 422


def test_request_survives_restart_and_approval_failure_does_not_consume(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://61.105.141.21:10443")
    sent = []
    path = str(tmp_path / "persist.db")
    def sender(*args):
        sent.append(args)
    with TestClient(create_app(path, SpeechService(""), approval_sender=sender)) as client:
        data, master = request(client, sent)
    with TestClient(create_app(path, SpeechService(""), approval_sender=sender)) as client:
        assert client.post(f"/api/master-approvals/{data['request_id']}/decision", headers=auth(master), json={"decision": "approve"}).status_code == 200
        assert client.post("/api/rooms", json=room_body(data, mode="invalid")).status_code == 422
        assert client.post("/api/rooms", json=room_body(data)).status_code == 201


def test_unconfigured_email_never_bypasses_approval(tmp_path, monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    with TestClient(create_app(str(tmp_path / "unconfigured.db"), SpeechService(""))) as client:
        config = client.get("/api/config").json()
        assert config["master_approval_required"] and not config["master_email_ready"]
        assert client.post("/api/host-approvals", json={"name": "방장", "contact": "host@example.com"}).status_code == 503
        assert client.post("/api/rooms", json={"name": "방장", "title": "회의"}).status_code == 403


def test_smtp_uses_tls_and_only_master_recipient(approval_client, monkeypatch):
    client, _ = approval_client
    service = client.app.state.approvals
    service.sender = None
    service.host, service.port, service.from_address = "smtp.example.com", 587, "sender@example.com"
    service.user, service.password = "sender@example.com", "not-a-real-password"
    calls = []
    class SMTP:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def ehlo(self): calls.append("ehlo")
        def starttls(self, **kwargs): calls.append("tls")
        def login(self, *args): calls.append("login")
        def send_message(self, message, **kwargs):
            assert message["To"] == MASTER_EMAIL
            assert kwargs["to_addrs"] == [MASTER_EMAIL]
            assert "host@example.com" in message.get_content()
            calls.append("send")
    monkeypatch.setattr("app.approvals.smtplib.SMTP", SMTP)
    service.send_mail("지현", "host@example.com", "https://example.com/master-approval#token=test")
    assert calls.index("tls") < calls.index("login") < calls.index("send")


def test_invalid_smtp_config_does_not_break_existing_server(tmp_path, monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "invalid")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://[")
    with TestClient(create_app(str(tmp_path / "invalid.db"), SpeechService(""))) as client:
        assert client.get("/api/health").json() == {"ok": True}
        assert not client.get("/api/config").json()["master_email_ready"]
