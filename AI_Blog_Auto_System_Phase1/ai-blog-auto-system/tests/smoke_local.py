"""Run a real loopback Uvicorn server and the CLI, without external services."""
import os
import hashlib
import sqlite3
import uuid
import asyncio
import inspect
import json
import websockets
from contextlib import closing
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import httpx

ROOT = Path(__file__).resolve().parents[1]

def main():
    with tempfile.TemporaryDirectory(prefix="blog-smoke-", dir=ROOT) as temporary:
        env = os.environ.copy()
        env["BLOG_DEVICE_TOKEN"] = secrets.token_urlsafe(32)
        env["BLOG_DB_PATH"] = str(Path(temporary) / "events.sqlite3")
        env["BLOG_OUTBOX_PATH"] = str(Path(temporary) / "outbox.sqlite3")
        env["BLOG_PACKAGE_DIR"] = str(Path(temporary) / "packages")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        env["BLOG_SERVER_URL"] = url
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app",
            "--app-dir", str(ROOT / "ubuntu-server"), "--host", "127.0.0.1", "--port", str(port)],
            env=env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            with httpx.Client(timeout=1, trust_env=False) as client:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError("Server exited before readiness")
                    try:
                        if client.get(url + "/api/v1/health").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.1)
                else:
                    raise RuntimeError("Server readiness timeout")
                for arguments in ([], ["--flush-only"]):
                    subprocess.run([sys.executable, str(ROOT / "windows-app/send_mock_event.py"), *arguments],
                                   cwd=ROOT, env=env, check=True, timeout=20)
                response = client.get(url + "/api/v1/events", headers={"X-Device-Token": env["BLOG_DEVICE_TOKEN"]})
                response.raise_for_status()
                assert len(response.json()) == 1
                assert response.json()[0]["event_type"] == "MOCK_PUBLISH_SUCCESS"
                print("PASS: real HTTP server + CLI + persisted event + empty retry")
                sys.path.insert(0, str(ROOT / "windows-app"))
                from blog_gui.exports import Publication
                article = {"id": str(uuid.uuid4()), "created_at": "2026-11-18T00:00:00+00:00",
                           "title": "HTTP smoke", "summary": "Local package", "sections": [],
                           "images": [], "sources": [], "tags": [], "seo_keywords": []}
                data = Publication(article).package()
                headers = {"X-Device-Token": env["BLOG_DEVICE_TOKEN"], "Content-Type": "application/zip",
                           "X-Content-SHA256": hashlib.sha256(data).hexdigest()}
                response = client.post(url + "/api/v1/packages", content=data, headers=headers)
                response.raise_for_status()
                package_id = response.json()["package_id"]
                endpoint = url + f"/api/v1/packages/{package_id}/download"
                assert client.get(endpoint, headers=headers).content == data
                assert client.get(endpoint).status_code == 401
                assert client.post(url + "/api/v1/packages", content=data, headers=headers).json()["new"] is False
                # Test DB only: prove HTTP denial without waiting for periodic deletion.
                with closing(sqlite3.connect(env["BLOG_DB_PATH"])) as db, db:
                    db.execute("UPDATE packages SET expires_at=? WHERE package_id=?",
                               ("2000-01-01T00:00:00+00:00", package_id))
                assert client.get(endpoint, headers=headers).status_code == 410
                assert len(list(Path(env["BLOG_PACKAGE_DIR"]).glob("*.zip"))) == 1
                print("PASS: real HTTP ZIP upload/download + auth + duplicate + immediate expiry denial")
                code = client.post(url + "/api/v1/pairing/codes", headers=headers).json()["code"]
                paired = client.post(url + "/api/v1/pairing/claim", json={"code": code, "device_name": "Android smoke"})
                paired.raise_for_status()
                mobile_headers = {"X-Device-Token": paired.json()["token"]}
                assert client.get(url + "/api/v1/packages", headers=mobile_headers).status_code == 200
                assert client.post(url + "/api/v1/events", json={}, headers=mobile_headers).status_code == 401
                after = client.get(url + "/api/v1/events", headers=headers).json()[0]["sequence"]
                async def check_socket():
                    options = {"additional_headers" if "additional_headers" in inspect.signature(websockets.connect).parameters else "extra_headers": mobile_headers}
                    if "proxy" in inspect.signature(websockets.connect).parameters:
                        options["proxy"] = None
                    async with websockets.connect(url.replace("http:", "ws:") + f"/api/v1/events/ws?after={after}", **options) as socket:
                        event_id = str(uuid.uuid4())
                        response = client.post(url + "/api/v1/events", headers={"X-Device-Token": env["BLOG_DEVICE_TOKEN"]},
                                               json={"event_id": event_id, "device_id": "PC", "event_type": "MANUAL_PUBLISH_REQUIRED"})
                        response.raise_for_status()
                        while True:
                            frame = json.loads(await asyncio.wait_for(socket.recv(), timeout=5))
                            if frame["type"] == "events":
                                assert frame["events"][0]["event_id"] == event_id
                                break
                asyncio.run(check_socket())
                print("PASS: real HTTP pairing + read-only token + live WebSocket event")
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

if __name__ == "__main__":
    main()
