"""Opt-in local Windows -> real HTTP/WS server -> Android JVM integration.

Never deploys or contacts Naver/Firebase. FCM adapter is a local file capture.
Requires JAVA_HOME, ANDROID_HOME and installed Android/Gradle dependencies.
"""
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "windows-app"))
sys.path.insert(0, str(ROOT / "ubuntu-server"))
import httpx
import uvicorn
from app.main import create_app
from blog_gui.services import Services
from blog_gui.storage import Store, Settings
from blog_gui.manual import ManualHandoff


def main():
    output = ROOT / "build" / "integration"
    output.mkdir(parents=True, exist_ok=True)
    checks = []
    def passed(name):
        checks.append(name)
        print("PASS: " + name, flush=True)
    with tempfile.TemporaryDirectory(prefix="integration-", dir=output) as temporary:
        directory = Path(temporary)
        push_file = directory / "push.jsonl"
        token = secrets.token_urlsafe(32)
        auth = {"X-Device-Token": token}
        now = [datetime.now(timezone.utc)]
        def capture(token, data):
            with push_file.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(data) + "\n")
        app = create_app(directory / "server.db", token, package_dir=directory / "packages",
                         clock=lambda: now[0], push_sender=capture)
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        origin = "http://127.0.0.1:" + str(sock.getsockname()[1])
        server = uvicorn.Server(uvicorn.Config(app, log_level="warning", ws="websockets-sansio"))
        thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 15
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Local server failed to start")
                time.sleep(.05)
            settings = Settings(server_url=origin)
            services = Services(Store(directory / "desktop"))
            services.record_login(settings, "성공")
            services.record_login(settings, "만료")
            article = services.write_article(settings, "", "통합 콘텐츠 전달 시험")
            article["images"] = []
            for caption in ("image-first", "image-second", "image-third"):
                image = services.generate_image(settings, "", caption)
                article["images"].append({**image, "id": caption, "caption": caption})
            handoff = ManualHandoff(services)
            path = handoff.prepare(settings, article, failed=True)
            # Real refused TCP connection, then recovery to the actual local server.
            blocked = socket.socket()
            blocked.bind(("127.0.0.1", 0))  # reserved but not listening
            original_origin = settings.server_url
            settings.server_url = "http://127.0.0.1:" + str(blocked.getsockname()[1])
            try:
                try:
                    services.send_mock(settings, token, flush_only=True)
                    raise AssertionError("Offline delivery unexpectedly succeeded")
                except httpx.ConnectError:
                    pass
                try:
                    handoff.upload(settings, token, path)
                    raise AssertionError("Offline upload unexpectedly succeeded")
                except httpx.ConnectError:
                    pass
            finally:
                blocked.close()
                settings.server_url = original_origin
            services = Services(Store(directory / "desktop"))
            handoff = ManualHandoff(services)
            assert services.send_mock(settings, token, flush_only=True) > 0
            metadata = handoff.retry(settings, token)[0]
            assert handoff.upload(settings, token, path)["new"] is False
            assert services.send_mock(settings, token, flush_only=True) == 0
            passed("Windows TCP outage/restart recovery + login/failure events + automatic ZIP + idempotent HTTP upload")
            with httpx.Client(base_url=origin, headers=auth) as client:
                code = client.post("/api/v1/pairing/codes").json()["code"]
                env = {**os.environ, "BLOG_INTEGRATION_URL": origin, "BLOG_INTEGRATION_CODE": code,
                       "BLOG_INTEGRATION_PACKAGE": article["id"], "BLOG_INTEGRATION_PUSH_FILE": str(push_file)}
                command = [str(ROOT / "android-app" / "gradlew.bat"), ":app:assembleDebug", ":app:testDebugUnitTest", ":app:lintDebug", "--no-daemon", "--console=plain"]
                result = subprocess.run(command, cwd=ROOT / "android-app", env=env, timeout=900)
                if result.returncode:
                    raise RuntimeError("Android integration/build failed")
                passed("Android Kotlin real HTTP pairing/download/SHA/image-order + WebSocket + manual completion + captured FCM payload/notification dedup")
                rows = client.get("/api/v1/events?after=0&limit=100").json()
                assert sum(r["event_type"] == "MANUAL_PUBLISH_COMPLETED" for r in rows) == 1
                assert not any(r["event_type"] == "PUBLISH_SUCCESS" for r in rows)
                expires = datetime.fromisoformat(metadata["expires_at"])
                download = f'/api/v1/packages/{article["id"]}/download'
                for hours in (6, 1):
                    now[0] = expires - timedelta(hours=hours)
                    app.state.packages.maintain()
                    app.state.packages.maintain()
                    rows = client.get("/api/v1/events?after=0&limit=100").json()
                    assert sum(r["event_type"] == f"PACKAGE_EXPIRING_{hours}H" for r in rows) == 1
                now[0] = expires - timedelta(microseconds=1)
                assert client.get(download).status_code == 200
                now[0] = expires
                assert client.get(download).status_code == 410
                assert list(app.state.packages.root.glob("*.zip"))
                app.state.packages.maintain()
                app.state.packages.maintain()
                assert not list(app.state.packages.root.glob("*.zip"))
                assert client.get(download).status_code == 410
                app.state.mobile.dispatch_push()
                captured = [json.loads(line) for line in push_file.read_text().splitlines()]
                for kind in ("PACKAGE_EXPIRING_6H", "PACKAGE_EXPIRING_1H", "PACKAGE_DELETED"):
                    assert any(row["event_type"] == kind for row in captured)
                passed("48h boundary 200->410 before cleanup + 6h/1h reminder dedup + file deletion + notification dispatch")
        finally:
            server.should_exit = True
            thread.join(15)
            sock.close()
            if thread.is_alive():
                raise RuntimeError("Local server did not stop")
    (output / "result.json").write_text(json.dumps({"at": datetime.now(timezone.utc).isoformat(),
        "checks": checks, "real_fcm": False, "ubuntu_os": False, "production_changed": False}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
