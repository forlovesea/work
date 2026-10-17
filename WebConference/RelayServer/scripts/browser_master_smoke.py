"""Local Master management test with temporary keys and no real email."""
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import uvicorn
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.main import create_app
from app.media import SpeechService
from app.master_auth import write_key

TEST_KEY = "local-browser-test-master-2026"


def main():
    output = ROOT / "test-results"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as temporary:
        key_path = Path(temporary) / "key.json"
        write_key(key_path, TEST_KEY)
        sent = []
        app = create_app(":memory:", SpeechService(""), master_key_path=key_path,
                         approval_sender=lambda *args: sent.append(args))
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=18081, log_level="warning"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        for _ in range(100):
            if server.started: break
            time.sleep(.1)
        assert server.started
        base = "http://127.0.0.1:18081"
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel="chrome", headless=True, args=[
                    "--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"])
                host = browser.new_page(viewport={"width": 1400, "height": 1000})
                master = browser.new_page(viewport={"width": 1400, "height": 1000})
                errors = []
                for page in (host, master):
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    page.goto(base)
                    page.wait_for_function("state.config !== null")
                host.locator("#name").fill("일반 방장")
                host.locator("#create-tab").click()
                host.locator("#title").fill("사용자가 만든 방")
                host.locator("#contact").fill("host@example.com")
                host.locator("#pref-mic").check()
                host.locator("#pref-camera").check()
                host.locator("#request-approval").click()
                host.wait_for_function("state.approval?.status === 'pending'")
                fields = parse_qs(urlsplit(sent[0][2]).fragment)
                result = host.request.post(base + f"/api/master-approvals/{fields['request'][0]}/decision",
                                           headers={"Authorization": "Bearer " + fields["token"][0]}, data={"decision": "approve"})
                assert result.ok
                expect(host.locator("#enter")).to_be_enabled(timeout=15000)
                host.locator("#enter").click()
                host.wait_for_function("state.publisher?.connectionState === 'connected'", timeout=30000)
                old_code = host.evaluate("state.session.code")
                assert host.evaluate("state.micTrack.readyState === 'live' && state.cameraTrack.readyState === 'live'")

                master.locator("#master-open").click()
                master.locator("#master-key").fill(TEST_KEY)
                master.locator("#master-login").click()
                expect(master.locator("#master-management")).to_be_visible()
                assert master.locator("#master-key").input_value() == ""
                master.locator("#master-create").click()
                expect(master.locator("#request-approval")).to_be_hidden()
                master.locator("#title").fill("Master 직접 생성")
                master.locator("#enter").click()
                expect(master.locator("#conference")).to_be_visible(timeout=30000)
                assert master.evaluate("me().is_master")
                master.locator("#master-open").click()
                expect(master.locator(".master-room")).to_have_count(2)
                master.screenshot(path=str(output / "master-management.png"), full_page=True)
                master.set_viewport_size({"width": 390, "height": 844})
                master.screenshot(path=str(output / "master-management-mobile.png"), full_page=True)
                assert master.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                master.on("dialog", lambda dialog: dialog.accept())
                master.locator(".master-room").filter(has_text="사용자가 만든 방").get_by_role("button", name="방에 입장").click()
                master.wait_for_function("state.room?.title === '사용자가 만든 방'", timeout=30000)
                assert master.evaluate("me().is_master && !isHost()")
                master.locator(".person").filter(has_text="일반 방장").get_by_role("button", name="강제 퇴장").click()
                expect(host.locator("#lobby")).to_be_visible(timeout=15000)
                assert host.evaluate("state.micTrack === null && state.cameraTrack === null && state.session === null")
                master.wait_for_function("isHost() && state.room.participants.length === 1")
                assert master.evaluate("state.room.code") != old_code
                assert host.request.post(base + "/api/join", data={"name": "재입장", "code": old_code}).status == 404
                master.locator("#master-open").click()
                master.locator(".master-room").filter(has_text="사용자가 만든 방").get_by_role("button", name="방 삭제").click()
                expect(master.locator("#lobby")).to_be_visible()
                expect(master.locator(".master-room")).to_have_count(0)
                write_key(key_path, "rotated-browser-test-master-2026")
                master.locator("#master-refresh").click()
                expect(master.locator("#master-login-form")).to_be_visible()
                assert master.evaluate("state.master === null")
                assert not errors, errors
                browser.close()
        finally:
            server.should_exit = True
            thread.join(timeout=15)
    print("OK: Master create, join user room, live media kick, rotated invite, delete, key reset, mobile; no real mail")


if __name__ == "__main__":
    main()
