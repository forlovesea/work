"""Real loopback API + Qt buttons + Windows Credential Manager smoke test.

Uses an isolated credential namespace, temporary databases and no paid APIs.
"""
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import uuid

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "windows-app"))

import httpx
from PySide6.QtWidgets import QApplication
from blog_gui.storage import Store, Vault
from blog_gui.window import MainWindow


def main():
    app = QApplication.instance() or QApplication([])
    vault = Vault("AI Blog Smoke Test " + str(uuid.uuid4()))
    token = secrets.token_urlsafe(32)
    window = None
    process = None
    with tempfile.TemporaryDirectory(prefix="blog-gui-smoke-", dir=ROOT) as temporary:
        try:
            vault.set("server", token)
            assert vault.get("server") == token
            store = Store(Path(temporary) / "desktop")
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            config = store.settings()
            config.server_url = f"http://127.0.0.1:{port}"
            config.initialized = True
            store.save_settings(config)
            env = os.environ.copy()
            env["BLOG_DEVICE_TOKEN"] = token
            env["BLOG_DB_PATH"] = str(Path(temporary) / "server.sqlite3")
            process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app",
                "--app-dir", str(ROOT / "ubuntu-server"), "--host", "127.0.0.1", "--port", str(port)],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with httpx.Client(timeout=1, trust_env=False) as client:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError("API exited before readiness")
                    try:
                        if client.get(config.server_url + "/api/v1/health").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.1)
                else:
                    raise RuntimeError("API readiness timeout")
                window = MainWindow(store, vault)
                window.show()
                def click(name, page):
                    window.nav.setCurrentRow(page)
                    app.processEvents()
                    window.buttons[name].click()
                    deadline = time.monotonic() + 15
                    while window.busy and time.monotonic() < deadline:
                        app.processEvents()
                        time.sleep(0.01)
                    assert not window.busy, name + " timed out"
                    app.processEvents()
                click("connect", 2)
                assert "ONLINE" in window.connection.text()
                click("send_event", 2)
                assert "1건" in window.connection.text()
                click("collect_news", 4)
                assert window.news_table.rowCount() == 3
                click("use_news", 4)
                window.review_source.setChecked(True)
                click("write_article", 5)
                assert window.article and window.article["mock"]
                click("generate_image", 6)
                assert window.image and Path(window.image["path"]).exists()
                click("flush", 2)
                response = client.get(config.server_url + "/api/v1/events", headers={"X-Device-Token": token})
                response.raise_for_status()
                assert {e["event_type"] for e in response.json()} == {"MOCK_PUBLISH_SUCCESS", "CONTENT_GENERATED", "IMAGE_GENERATED"}
                output = ROOT / ".pytest-tmp"
                output.mkdir(exist_ok=True)
                for page, name in [(0, "dashboard"), (5, "writer"), (6, "image")]:
                    window.nav.setCurrentRow(page)
                    app.processEvents()
                    assert window.grab().save(str(output / f"gui-{name}.png"))
                print("PASS: Qt GUI buttons + real HTTP auth/events + Mock news/article/PNG + encrypted credentials")
                print("PASS: 3 event types persisted on Phase 1 server; no external service requests")
        finally:
            if window is not None:
                window.close()
                app.processEvents()
            if process is not None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            vault.set("server", "")
            assert vault.get("server") == ""


if __name__ == "__main__":
    main()
