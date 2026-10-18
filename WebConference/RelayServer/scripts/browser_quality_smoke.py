"""Local WebRTC quality UI, real fake-camera tracks, and deterministic bad-link tests."""
import sys
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.main import create_app
from app.media import SpeechService


def main():
    output = ROOT / "test-results"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as temporary:
        app = create_app(":memory:", SpeechService(""), approval_required=False,
                         master_key_path=Path(temporary)/"missing-key.json")
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=18082, log_level="warning"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        for _ in range(100):
            if server.started: break
            time.sleep(.1)
        assert server.started
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel="chrome", headless=True, args=[
                    "--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"])
                page = browser.new_page(viewport={"width":1440,"height":1000})
                errors=[]
                page.on("pageerror",lambda e: errors.append(str(e)))
                page.goto("http://127.0.0.1:18082")
                page.wait_for_function("state.config !== null")
                assert page.evaluate("[50,200,400,600,900].map(rtt=>MoaQuality.grade({rtt}))") == [5,4,3,2,1]
                assert page.evaluate("MoaQuality.grade({})") == 0
                assert page.evaluate("MoaQuality.grade({rtt:10,loss:12,jitter:1})") == 1
                assert page.evaluate("""() => { const a=new MoaQuality.AutoProfile();
                  const results=[];for(let i=0;i<5;i++) results.push(a.update({level:5,outgoing:3000000}));
                  results.push(a.update({level:1}));results.push(a.update({level:1}));return results;
                }""") == ['medium']*4+['high','high','low']
                assert page.evaluate("""async () => {
                  let received=100,lost=0;
                  const pc={connectionState:'connected',getStats:async()=>new Map([
                    ['pair',{id:'pair',type:'candidate-pair',state:'succeeded',nominated:true,currentRoundTripTime:.04}],
                    ['in',{id:'in',type:'inbound-rtp',timestamp:performance.now(),packetsReceived:received,packetsLost:lost,jitter:.01}]
                  ])};
                  const sampler=new MoaQuality.Sampler();await sampler.read(pc);received=180;lost=20;
                  const bad=await sampler.read(pc);received=280;const recovered=await sampler.read(pc);
                  pc.connectionState='failed';const failed=await sampler.read(pc);
                  return [bad.loss,recovered.loss,bad.level,recovered.level,failed.level];
                }""") == [20,0,1,5,1]
                page.locator('#name').fill('화질 검증 방장')
                page.locator('#create-tab').click()
                page.locator('#title').fill('통신 상태와 자동 화질')
                page.locator('#pref-camera').check()
                page.locator('#enter').click()
                page.wait_for_function("state.publisher?.connectionState==='connected'",timeout=30000)
                expect(page.locator('#camera-quality')).to_have_value('auto')
                page.wait_for_function("document.querySelector('#network-quality').dataset.level !== '0'",timeout=20000)
                # Actual getStats + aiortc connection above; deterministic adaptation below.
                page.evaluate("clearInterval(qualityTimer)")
                page.wait_for_function('!qualityBusy')
                for selection, height, bitrate in [('low',360,350000),('high',720,1500000),('full',1080,2500000)]:
                    page.locator('#camera-quality').select_option(selection)
                    page.wait_for_function(f"!document.querySelector('#camera-quality').disabled && state.cameraTrack.getSettings().height === {height}")
                    assert page.evaluate("state.publisher.getSenders().find(s=>s.track?.kind==='video').getParameters().encodings[0].maxBitrate") == bitrate
                page.locator('#camera-quality').select_option('auto')
                expect(page.locator('#camera-quality')).to_be_enabled()
                page.evaluate("qualitySampler.read=async()=>({level:1,rtt:900,loss:15,jitter:160,outgoing:250000})")
                page.evaluate('async()=>{await sampleQuality();await sampleQuality()}')
                assert page.evaluate('state.cameraTrack.getSettings().height') == 360
                expect(page.locator('#network-label')).to_have_text('매우 불안정 1/5')
                page.evaluate("qualitySampler.read=async()=>({level:5,rtt:50,loss:0,jitter:5,outgoing:3000000})")
                page.evaluate('async()=>{for(let i=0;i<5;i++) await sampleQuality()}')
                assert page.evaluate('state.cameraTrack.getSettings().height') == 720
                # A poor receive-only path affects the badge, not our upload adaptation.
                page.evaluate("""async()=>{
                  state.peers.set('test-path', {});
                  qualitySampler.read=async pc=>pc===state.publisher?{level:5,outgoing:3000000}:{level:1,loss:20};
                  await sampleQuality();await sampleQuality();state.peers.delete('test-path');
                }""")
                assert page.evaluate('state.cameraTrack.getSettings().height') == 720
                expect(page.locator('#network-label')).to_have_text('매우 불안정 1/5')
                page.evaluate("qualitySampler.read=async()=>({level:5,rtt:50,loss:0,jitter:5,outgoing:3000000})")
                page.evaluate('sampleQuality()')
                page.screenshot(path=str(output/'quality-desktop.png'))
                # Manual mode is not overridden by the automatic controller.
                page.locator('#camera-quality').select_option('medium')
                expect(page.locator('#camera-quality')).to_be_enabled()
                page.evaluate("qualitySampler.read=async()=>({level:1,rtt:900,loss:15,jitter:160})")
                page.evaluate('async()=>{await sampleQuality();await sampleQuality()}')
                assert page.evaluate('state.cameraTrack.getSettings().height') == 540
                # Screen track shares the sender but must not inherit the webcam bitrate cap.
                assert page.evaluate('''async()=>{
                  const c=document.createElement('canvas');c.width=1280;c.height=720;
                  state.shareTrack=c.captureStream(15).getVideoTracks()[0];
                  await replaceTrack('video',state.shareTrack);await applyCameraQuality();
                  return state.publisher.getSenders().find(s=>s.track?.kind==='video').getParameters().encodings[0].maxBitrate===undefined;
                }''')
                page.locator('#camera-quality').select_option('low')
                expect(page.locator('#camera-quality')).to_be_enabled()
                assert page.evaluate('state.shareTrack.getSettings().width') == 1280
                page.evaluate('stopShare(false)')
                assert page.evaluate("state.publisher.getSenders().find(s=>s.track?.kind==='video').getParameters().encodings[0].maxBitrate") == 350000
                page.locator('#toggle-camera').click()
                page.wait_for_function('state.cameraTrack===null')
                page.locator('#toggle-camera').click()
                page.wait_for_function('state.cameraTrack?.getSettings().height===360')
                page.set_viewport_size({'width':390,'height':844})
                page.locator('.view-bar').scroll_into_view_if_needed()
                page.locator('#network-quality summary').click()
                page.screenshot(path=str(output/'quality-mobile.png'))
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.locator('#leave').click()
                page.wait_for_function('state.publisher===null && qualityTimer===null')
                assert page.evaluate("qualityMode==='auto' && state.cameraTrack===null")
                assert not errors,errors
                browser.close()
                print('PASS: live WebRTC, five grades, loss deltas, hysteresis, manual/auto resolution+bitrate, screen isolation, camera toggle, mobile, cleanup')
        finally:
            server.should_exit=True
            thread.join(timeout=15)


if __name__ == '__main__':
    main()
