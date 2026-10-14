import asyncio
from fractions import Fraction
from pathlib import Path

import pytest
from aiortc import AudioStreamTrack, RTCConfiguration, RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import AudioFrame

from app.domain import Participant, Room, Store, minutes_markdown
from app.main import Hub
from app.media import AudioGate, SpeechService


def test_model_failure_reports_low_windows_commit(monkeypatch, tmp_path):
    import vosk
    from app import media

    def fail_model(path):
        raise RuntimeError("Native model allocation failed")

    monkeypatch.setattr(vosk, "Model", fail_model)
    monkeypatch.setattr(media, "windows_available_commit", lambda: 100 * 1024 * 1024)
    speech = SpeechService(str(tmp_path))
    assert not speech.available
    assert "메모리" in speech.error
    monkeypatch.setattr(media, "windows_available_commit", lambda: None)
    assert "서버 로그" in SpeechService(str(tmp_path)).error


class Tone(AudioStreamTrack):
    async def recv(self):
        frame = await super().recv()
        for plane in frame.planes:
            plane.update(b"\x10\x27" * (plane.buffer_size // 2))
        return frame


async def test_audio_gate_drops_unauthorized_samples():
    allowed = False
    gate = AudioGate(Tone(), lambda: allowed)
    silent = await gate.recv()
    assert not any(bytes(silent.planes[0]))
    allowed = True
    audible = await gate.recv()
    assert any(bytes(audible.planes[0]))
    assert audible.pts > silent.pts
    allowed = False
    assert not any(bytes((await gate.recv()).planes[0]))
    gate.stop()


async def test_real_webrtc_relay_audio_video_and_floor_switch():
    store = Store(":memory:")
    hub = Hub(store, SpeechService(""))
    room = Room("r", "CODE", "Relay test", "meeting", "", False)
    host = hub.add_person(room, "Host")
    guest = hub.add_person(room, "Guest")
    room.host_id = room.presenter_id = host.id
    host.connected = guest.connected = True
    host.mic = True
    store.add_room(room)
    hub.rooms[room.id] = room
    publisher = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    subscriber = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    publisher.addTrack(Tone()); publisher.addTrack(VideoStreamTrack())
    received = {}

    @subscriber.on("track")
    def on_track(track):
        received[track.kind] = track

    try:
        await publisher.setLocalDescription(await publisher.createOffer())
        answer = await hub.publish(room, host, publisher.localDescription.sdp)
        await publisher.setRemoteDescription(RTCSessionDescription(**answer))
        subscriber.addTransceiver("audio", direction="recvonly")
        subscriber.addTransceiver("video", direction="recvonly")
        await subscriber.setLocalDescription(await subscriber.createOffer())
        answer = await hub.subscribe(room, guest, host.id, subscriber.localDescription.sdp)
        await subscriber.setRemoteDescription(RTCSessionDescription(**answer))
        frame = await asyncio.wait_for(received["video"].recv(), 15)
        assert frame.width == 640 and frame.height == 480
        audio = await asyncio.wait_for(received["audio"].recv(), 10)
        assert any(bytes(audio.planes[0]))
        room.set_presenter(host.id, guest.id)
        # Allow in-flight audio and the Opus decoder's transition tail to drain.
        quiet = False
        for _ in range(100):
            audio = await asyncio.wait_for(received["audio"].recv(), 5)
            samples = memoryview(bytes(audio.planes[0])).cast("h")
            if max(map(abs, samples)) < 50:
                quiet = True
                break
        assert quiet, "Previous presenter's audio must be silenced by server"
    finally:
        await publisher.close(); await subscriber.close()
        await hub.remove(room, host); await hub.remove(room, guest)
        store.db.close()


def test_minutes_do_not_promote_transcript_to_confirmed_decision():
    room = Room("r", "CODE", "회의", "meeting", "h", True)
    entries = [{"speaker": "민수", "text": "아직 결정하지 않았습니다", "kind": "speech", "at": "2026-10-14T01:00:00+00:00"}]
    output = minutes_markdown(room, entries)
    confirmed = output.split("## 확정 결정 (방장 기록)")[1].split("## 실행 항목")[0]
    assert "결정하지" not in confirmed
    assert "미확정" in output and "시간순 원문" in output


async def test_installed_korean_model_processes_audio_and_floor_changes():
    model = Path(__file__).resolve().parents[1] / "models" / "vosk-model-small-ko-0.22"
    if not (model / "am" / "final.mdl").exists():
        pytest.skip("Install Korean Vosk model to run recognition smoke test")
    speech = SpeechService(str(model))
    assert speech.available
    person = Participant("p", "발표자", connected=True, mic=True)
    room = Room("r", "CODE", "음성 검증", "meeting", "p", True, participants={"p": person}, presenter_id="p")
    events = []

    async def emit(room, participant, text, error=None):
        events.append((text, error))

    track = AudioStreamTrack()
    task = asyncio.create_task(speech.transcribe(track, room, person, emit))
    await asyncio.sleep(0.7)
    room.set_minutes("p", False, speech.available)
    await asyncio.sleep(0.15)
    room.set_minutes("p", True, speech.available)
    await asyncio.sleep(0.4)
    task.cancel()
    await task
    assert not any(error for _, error in events)
    assert not any(text for text, _ in events), "Silence should not fabricate speech"
