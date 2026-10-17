"""Three isolated real browsers, synthetic camera/mic. Run localhost:8000 first."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "test-results"


def main():
    OUTPUT.mkdir(exist_ok=True)
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True, args=[
            "--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream",
            "--autoplay-policy=no-user-gesture-required",
        ])
        host_context = browser.new_context(viewport={"width": 1440, "height": 1050})
        guest_context = browser.new_context(viewport={"width": 1440, "height": 1050})
        observer_context = browser.new_context(viewport={"width": 1440, "height": 1050})
        host, guest = host_context.new_page(), guest_context.new_page()
        observer = observer_context.new_page()
        for page in (host, guest):
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto("http://localhost:8000")
            page.wait_for_function("document.querySelector('#server-state').textContent.includes('연결됨')")
            assert not page.locator("#pref-mic").is_checked()
            assert not page.locator("#pref-speaker").is_checked()
        host.screenshot(path=str(OUTPUT / "01-lobby.png"), full_page=True)
        host.locator("#name").fill("지민 · 방장")
        host.locator("#create-tab").click()
        host.locator("#title").fill("제품팀 아이디어 회의")
        host.locator("#pref-camera").check()
        if host.locator("#pref-minutes").is_enabled():
            host.locator("#pref-minutes").check()
        host.locator("#enter").click()
        host.wait_for_function("state.publisher?.connectionState === 'connected'", timeout=30000)
        code = host.evaluate("state.session.code")
        invite = host.locator("#invite-link").input_value()
        assert invite == f"http://localhost:8000/#room={code}"
        assert host.evaluate("state.session.token") not in invite
        host_context.grant_permissions(["clipboard-read", "clipboard-write", "camera", "microphone"])
        host.locator("#copy-invite").click()
        assert host.evaluate("navigator.clipboard.readText()") == invite
        host.screenshot(path=str(OUTPUT / "06-host-invite.png"), full_page=True)
        host.set_viewport_size({"width": 390, "height": 844})
        assert host.evaluate("document.documentElement.scrollWidth <= innerWidth")
        host.screenshot(path=str(OUTPUT / "07-mobile-invite.png"), full_page=True)
        host.set_viewport_size({"width": 1440, "height": 1050})
        # Existing saved settings must not redirect an invite to another server.
        guest.evaluate("localStorage.setItem('moa-settings', JSON.stringify({server: 'https://wrong.invalid', name: 'Saved guest'}))")
        guest.goto("about:blank")
        guest.goto(invite)
        assert guest.locator("#server").input_value() == "http://localhost:8000"
        assert guest.locator("#code").input_value() == code
        assert guest.locator("#name").input_value() == "Saved guest"
        assert guest.locator("#invite-notice").is_visible()
        assert guest.evaluate("state.session === null && state.local === null")
        for device in ("mic", "speaker", "camera"):
            assert not guest.locator(f"#pref-{device}").is_checked()
        guest.screenshot(path=str(OUTPUT / "08-invite-landing.png"), full_page=True)
        guest.locator("#name").fill("서준 · 참석자")
        guest.locator("#pref-camera").check()
        guest.locator("#enter").click()
        for page in (host, guest):
            page.wait_for_function("state.room?.participants.length === 2 && [...state.peers.values()].some(pc => pc.connectionState === 'connected')", timeout=30000)
            page.wait_for_function("[...document.querySelectorAll('#grid video')].every(v => v.videoWidth > 0)", timeout=30000)
            assert page.evaluate("[...document.querySelectorAll('#remote-audio audio')].every(a => a.muted)")
        assert guest.locator("#host-invite").is_hidden()
        # Clipboard denial must leave a selectable link for manual copying.
        host.evaluate("() => { window.originalClipboardWrite = navigator.clipboard.writeText; navigator.clipboard.writeText = async () => { throw new Error('denied'); }; }")
        host.locator("#copy-invite").click()
        host.wait_for_function("document.querySelector('#toast').textContent.includes('Ctrl+C')")
        assert host.locator("#invite-link").evaluate("el => el.selectionEnd - el.selectionStart === el.value.length")
        host.evaluate("() => { navigator.clipboard.writeText = window.originalClipboardWrite; }")
        observer.on("pageerror", lambda error: errors.append(str(error)))
        observer.goto(invite)
        observer.locator("#name").fill("하윤 · 참관")
        observer.locator("#code").fill(code)
        observer.locator("#enter").click()
        for page in (host, guest, observer):
            page.wait_for_function("state.room?.participants.length === 3 && [...state.peers.values()].filter(pc => pc.connectionState === 'connected').length === 2", timeout=30000)
        assert observer.evaluate("state.micTrack === null && state.cameraTrack === null && !state.speaker")
        host.locator("#toggle-mic").click()
        guest.locator("#toggle-mic").click()
        guest.wait_for_function("document.querySelector('#toggle-mic b').textContent === '마이크 대기'")
        guest.locator("#hand").click()
        host.wait_for_function("state.room.hands.length === 1")
        host.locator(".person").filter(has_text="서준").get_by_role("button", name="발표 지정").click()
        guest.wait_for_function("me().can_speak === true")
        host.wait_for_function("me().can_speak === false")
        assert host.evaluate("state.micTrack.enabled === false")
        assert guest.evaluate("state.micTrack.enabled === true")
        host.screenshot(path=str(OUTPUT / "02-meeting.png"), full_page=True)
        guest.locator('[data-view="board"]').click()
        board = guest.locator("#board").bounding_box()
        guest.mouse.move(board["x"] + 80, board["y"] + 80)
        guest.mouse.down()
        guest.mouse.move(board["x"] + 260, board["y"] + 160, steps=15)
        guest.mouse.up()
        host.wait_for_function("state.strokes.length > 0")
        host.locator('[data-view="board"]').click()
        host.screenshot(path=str(OUTPUT / "03-whiteboard.png"), full_page=True)
        host.locator("#notes-tab").click()
        host.locator("#note-kind").select_option("decision")
        host.locator("#note-text").fill("다음 주 수요일에 시제품을 함께 검토한다.")
        host.locator('#note-form button').click()
        guest.wait_for_function("state.entries.some(e => e.kind === 'decision')")
        assert not host.locator("#minutes-summary").is_checked()
        assert host.locator("#minutes-format").input_value() == "docx"
        from docx import Document
        from pypdf import PdfReader
        for fmt in ("docx", "pdf", "txt"):
            host.locator("#minutes-format").select_option(fmt)
            host.locator("#minutes-summary").set_checked(fmt == "pdf")
            with host.expect_download() as download:
                host.locator("#download").click()
            assert download.value.suggested_filename.endswith("." + fmt)
            path = OUTPUT / ("meeting-minutes." + fmt)
            download.value.save_as(str(path))
            if fmt == "docx":
                text = "\n".join(p.text for p in Document(path).paragraphs)
            elif fmt == "pdf":
                text = "\n".join(p.extract_text() for p in PdfReader(path).pages)
            else:
                text = path.read_text(encoding="utf-8-sig")
            assert "시제품" in text and "전체 대화 및 기록" in text
            assert ("회의록 요약" in text) == (fmt == "pdf")
        host.locator('[data-view="focus"]').click()
        host.wait_for_function("document.querySelector('#focus-video').readyState >= 2 && document.querySelector('#focus-video').videoWidth > 0")
        host.screenshot(path=str(OUTPUT / "04-minutes.png"), full_page=True)
        host.locator("#leave").click()
        guest.wait_for_function("isHost() === true")
        assert guest.locator("#host-invite").is_visible()
        assert guest.locator("#invite-link").input_value() == invite
        guest.locator("#leave").click()
        observer.wait_for_function("isHost() === true")
        observer.locator("#leave").click()
        guest.goto("http://localhost:8000/#room=invalid-code")
        assert guest.locator("#code").input_value() == ""
        assert "올바르지" in guest.locator("#invite-notice").inner_text()
        assert guest.evaluate("state.session === null")
        host.set_viewport_size({"width": 390, "height": 844})
        host.screenshot(path=str(OUTPUT / "05-mobile-lobby.png"), full_page=True)
        assert host.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert not errors, errors
        browser.close()
    print(json.dumps({"ok": True, "checks": ["invite copy and clipboard fallback", "invite prefill overrides saved server", "invite requires explicit join", "invalid invite", "host-only invite panel and transfer", "device defaults", "three browsers", "video received", "speaker muted", "floor switch", "whiteboard sync", "minutes export", "host transfer", "mobile width", "no JS errors"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
