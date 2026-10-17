"""Local-only UI approval test. Captures mail in memory; never sends email."""
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.main import create_app
from app.media import SpeechService


def main():
    sent = []
    app = create_app(":memory:", SpeechService(""), approval_sender=lambda *args: sent.append(args))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=18080, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started: break
        time.sleep(.1)
    assert server.started
    base = "http://127.0.0.1:18080"
    output = ROOT / "test-results"
    output.mkdir(exist_ok=True)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome", headless=True)
            host = browser.new_page(viewport={"width": 1400, "height": 1100})
            master = browser.new_page(viewport={"width": 800, "height": 900})
            errors = []
            host.on("pageerror", lambda e: errors.append(str(e)))
            master.on("pageerror", lambda e: errors.append(str(e)))
            host.goto(base)
            host.wait_for_function("state.config?.master_email_ready")
            host.locator("#name").fill("승인 테스트 방장")
            host.locator("#create-tab").click()
            host.locator("#title").fill("Master 승인 회의")
            host.locator("#contact").fill("host@example.com")
            expect(host.locator("#enter")).to_be_disabled()
            host.locator("#request-approval").click()
            host.wait_for_function("state.approval?.status === 'pending'")
            assert len(sent) == 1 and sent[0][:2] == ("승인 테스트 방장", "host@example.com")
            host.screenshot(path=str(output / "approval-pending.png"), full_page=True)
            # A reload retains the request in this tab, but not in unrelated tabs.
            host.reload()
            host.locator("#create-tab").click()
            host.locator("#title").fill("Master 승인 회의")
            expect(host.locator("#enter")).to_be_disabled()
            link = urlsplit(sent[0][2])
            master.goto(base + link.path + "#" + link.fragment)
            expect(master.locator("#request-name")).to_have_text("승인 테스트 방장")
            expect(master.locator("#request-contact")).to_have_text("host@example.com")
            assert "#" not in master.url
            expect(host.locator("#enter")).to_be_disabled()
            master.screenshot(path=str(output / "approval-master.png"), full_page=True)
            master.locator("#approve-host").click()
            expect(master.locator("#approval-result")).to_contain_text("인증이 완료")
            expect(host.locator("#enter")).to_be_enabled(timeout=15000)
            host.set_viewport_size({"width": 390, "height": 844})
            host.screenshot(path=str(output / "approval-mobile.png"), full_page=True)
            assert host.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            host.locator("#enter").click()
            expect(host.locator("#conference")).to_be_visible(timeout=30000)
            host.locator("#leave").click()
            expect(host.locator("#enter")).to_be_disabled()
            host.locator("#contact").fill("second@example.com")
            host.locator("#request-approval").click()
            host.wait_for_function("state.approval?.status === 'pending'")
            link = urlsplit(sent[1][2])
            master.goto(base + link.path + "#" + link.fragment)
            master.locator("#reject-host").click()
            host.wait_for_function("state.approval?.status === 'rejected'", timeout=15000)
            expect(host.locator("#enter")).to_be_disabled()
            assert not errors, errors
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=15)
    print("OK: pending, refresh, Master-only approval, single use, rejection, mobile, no JS errors; no real mail sent")


if __name__ == "__main__":
    main()
