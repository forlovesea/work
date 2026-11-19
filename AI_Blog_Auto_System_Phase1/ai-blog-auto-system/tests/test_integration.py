"""Windows handoff -> server -> paired mobile contract, with injected failures/time."""
import hashlib
import json
import sys
from pathlib import Path
from contextlib import closing
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ubuntu-server"))
sys.path.insert(0, str(ROOT / "windows-app"))
from app.main import create_app
from blog_gui.manual import ManualHandoff, automatic_publish, AUTO_PUBLISH_ENABLED
from blog_gui.services import Services, ServiceError
from blog_gui.storage import Store, Settings
from test_phase4 import Clock, AUTH, TOKEN, package, upload
from test_phase5 import pair


def test_windows_failure_handoff_network_recovery_and_retention(tmp_path):
    clock = Clock()
    pushed = []
    app = create_app(tmp_path / "server.db", TOKEN, package_dir=tmp_path / "private", clock=clock,
                     push_sender=lambda token, data: pushed.append(data))
    desktop = Store(tmp_path / "desktop")
    config = Settings()
    offline = True
    lose_ack = False
    with TestClient(app) as client:
        def transport(request):
            nonlocal lose_ack
            if offline:
                raise httpx.ConnectError("injected offline", request=request)
            response = client.request(request.method, request.url.path, content=request.content, headers=request.headers)
            if lose_ack and request.url.path == "/api/v1/packages":
                lose_ack = False
                raise httpx.ReadError("injected lost upload acknowledgement", request=request)
            return response
        factory = lambda: httpx.Client(transport=httpx.MockTransport(transport))
        services = Services(desktop, factory)
        device, _ = pair(client)
        mobile = {"X-Device-Token": device["token"]}
        assert client.put("/api/v1/devices/me/push", headers=mobile, json={"token": "integration-fake-fcm-token"}).status_code == 200
        for state in ("성공", "실패", "만료"):
            services.record_login(config, state)
        article = services.write_article(config, "", "통합 시험")
        article["images"] = []
        for color in ("first", "second", "third"):
            image = services.generate_image(config, "", color)
            article["images"].append({**image, "id": color, "caption": color})
        handoff = ManualHandoff(services)
        path = handoff.prepare(config, article, failed=True)
        original = path.read_bytes()
        with pytest.raises(httpx.ConnectError):
            handoff.upload(config, TOKEN, path)
        with pytest.raises(httpx.ConnectError):
            services.send_mock(config, TOKEN, flush_only=True)
        assert path.read_bytes() == original
        # Restart Windows services and lose the first successful server response.
        offline, lose_ack = False, True
        services = Services(Store(desktop.directory), factory)
        handoff = ManualHandoff(services)
        with pytest.raises(httpx.ReadError):
            handoff.retry(config, TOKEN)
        result = handoff.retry(config, TOKEN)[0]
        assert result["new"] is False
        assert result["sha256"] == hashlib.sha256(original).hexdigest()
        assert handoff.retry(config, TOKEN) == []
        assert services.send_mock(config, TOKEN, flush_only=True) > 0
        assert services.send_mock(config, TOKEN, flush_only=True) == 0
        url = f'/api/v1/packages/{article["id"]}'
        assert client.get(url + "/download", headers=mobile).content == original
        completion = {"confirmed": True, "post_url": "https://blog.naver.com/integration/123"}
        assert client.post(url + "/manual-completion", headers=mobile, json=completion).json()["new"]
        assert client.post(url + "/manual-completion", headers=mobile, json=completion).json()["new"] is False
        app.state.mobile.dispatch_push()
        kinds = [r["event_type"] for r in client.get("/api/v1/events?after=0&limit=100", headers=mobile).json()]
        for kind in ("NAVER_LOGIN_SUCCESS", "NAVER_LOGIN_FAILED", "NAVER_LOGIN_EXPIRED", "PUBLISH_FAILED",
                     "MANUAL_PUBLISH_REQUIRED", "PACKAGE_UPLOAD_SUCCESS", "MANUAL_PUBLISH_COMPLETED"):
            assert kinds.count(kind) == 1
            assert any(p["event_type"] == kind for p in pushed)
        assert "PUBLISH_SUCCESS" not in kinds
        expiry = clock.now + timedelta(hours=48)
        for remaining, kind in ((6, "PACKAGE_EXPIRING_6H"), (1, "PACKAGE_EXPIRING_1H")):
            clock.now = expiry - timedelta(hours=remaining)
            app.state.packages.maintain()
            app.state.packages.maintain()
            rows = client.get("/api/v1/events?after=0&limit=100", headers=mobile).json()
            assert sum(r["event_type"] == kind for r in rows) == 1
        clock.now = expiry
        assert client.get(url + "/download", headers=mobile).status_code == 410
        assert list(app.state.packages.root.glob("*.zip"))  # denied before cleanup
        app.state.packages.maintain()
        assert not list(app.state.packages.root.glob("*.zip"))
        assert client.get(url + "/download", headers=mobile).status_code == 410
        assert not AUTO_PUBLISH_ENABLED
        with pytest.raises(ServiceError):
            automatic_publish(article)


def test_manual_completion_auth_validation_conflict_and_expiry(tmp_path, package):
    clock = Clock()
    app = create_app(tmp_path / "server.db", TOKEN, clock=clock)
    with TestClient(app) as client:
        device, _ = pair(client)
        mobile = {"X-Device-Token": device["token"]}
        metadata = upload(client, package).json()
        url = f'/api/v1/packages/{metadata["package_id"]}/manual-completion'
        body = {"confirmed": True, "post_url": "https://blog.naver.com/test/123"}
        assert client.post(url, json=body).status_code == 401
        assert client.post(url, headers=mobile, json={**body, "confirmed": False}).status_code == 422
        assert client.post(url, headers=mobile, json={**body, "confirmed": "true"}).status_code == 422
        for invalid in ("https://blog.naver.com.evil.test/post", "http://blog.naver.com/test/123", "https://user@blog.naver.com/x", "https://blog.naver.com/"):
            assert client.post(url, headers=mobile, json={**body, "post_url": invalid}).status_code == 422
        assert client.post(url, headers=mobile, json=body).json()["verified"] is False
        assert client.post(url, headers=mobile, json={**body, "post_url": body["post_url"] + "4"}).status_code == 409
        # A new completion at the exact expiry boundary is refused.
        with closing(app.state.packages.connect()) as db, db:
            db.execute("DELETE FROM events WHERE event_type='MANUAL_PUBLISH_COMPLETED'")
        clock.now += timedelta(hours=48)
        assert client.post(url, headers=mobile, json=body).status_code == 410


def test_maintenance_uses_five_minute_retry_interval(tmp_path, monkeypatch):
    import asyncio
    app = create_app(tmp_path / "server.db", TOKEN)
    stop = asyncio.Event()
    intervals, attempts = [], []
    def maintain():
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError("injected disk failure")
    async def wait(awaitable, timeout):
        awaitable.close()
        intervals.append(timeout)
        if len(intervals) == 1:
            raise asyncio.TimeoutError
        stop.set()
    monkeypatch.setattr(app.state.packages, "maintain", maintain)
    monkeypatch.setattr(asyncio, "wait_for", wait)
    asyncio.run(app.state.packages.maintenance_loop(300, stop))
    assert intervals == [300, 300]
    assert len(attempts) == 2


def test_windows_handoff_buttons(qtbot, tmp_path):
    from blog_gui.window import MainWindow
    from test_phase2 import MemoryVault, click
    app = create_app(tmp_path / "server.db", TOKEN)
    store = Store(tmp_path / "desktop")
    vault = MemoryVault()
    vault.set("server", TOKEN)
    with TestClient(app) as client:
        def transport(request):
            return client.request(request.method, request.url.path, content=request.content, headers=request.headers)
        services = Services(store, lambda: httpx.Client(transport=httpx.MockTransport(transport)))
        window = MainWindow(store, vault, services, browser=lambda url: True)
        qtbot.addWidget(window)
        try:
            article = services.write_article(window.config, "", "GUI 통합")
            window.display_article(article)
            window.login_state.setCurrentText("만료")
            click(qtbot, window, "record_login", 7)
            click(qtbot, window, "failed_upload", 9)
            metadata = store.get("uploaded:" + article["id"])
            assert metadata and metadata["new"] is True
            click(qtbot, window, "manual_upload", 9)
            assert store.get("uploaded:" + article["id"])["new"] is False
            click(qtbot, window, "retry_packages", 9)
            rows = client.get("/api/v1/events?after=0&limit=100", headers=AUTH).json()
            for kind in ("NAVER_LOGIN_EXPIRED", "PUBLISH_FAILED", "PACKAGE_UPLOAD_SUCCESS"):
                assert sum(r["event_type"] == kind for r in rows) == 1
        finally:
            qtbot.waitUntil(lambda: not window.busy, timeout=15000)
            window.close()
