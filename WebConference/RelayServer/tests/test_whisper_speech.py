import asyncio
import threading
from types import SimpleNamespace

import pytest
from aiortc import AudioStreamTrack

from app.domain import Participant, Room, Store
from app.whisper_speech import WhisperSpeechService


def context():
    person = Participant("p", "Speaker", connected=True, mic=True)
    room = Room("r", "CODE", "Test", "meeting", "p", True,
                participants={"p": person}, presenter_id="p")
    return room, person


async def test_inference_off_event_loop_and_original_timestamp():
    main_thread = threading.get_ident()
    events = []

    class Model:
        def transcribe(self, audio, **options):
            assert threading.get_ident() != main_thread
            assert options["language"] == "ko" and options["vad_filter"]
            assert options["beam_size"] == 5
            def segments():
                assert threading.get_ident() != main_thread
                yield SimpleNamespace(text=" recognized ", avg_logprob=-0.2, no_speech_prob=0.1)
                yield SimpleNamespace(text="hallucination", avg_logprob=-2, no_speech_prob=0.9)
            return segments(), None

    speech = WhisperSpeechService("", model=Model())
    room, person = context()
    async def emit(room, participant, text, **kwargs):
        events.append((participant.id, text, kwargs))
    await speech.submit(b"\x00\x01" * 16000, room, person, emit, "2026-10-17T01:00:00+00:00")
    assert speech.outstanding(room) == 1
    await asyncio.wait_for(speech.queue.join(), 5)
    assert events == [("p", "recognized", {"at": "2026-10-17T01:00:00+00:00"})]
    assert speech.outstanding(room) == 0
    await speech.close()


async def test_queue_overflow_is_visible_and_failure_does_not_stop_worker():
    speech = WhisperSpeechService("", model=object(), queue_size=1)
    room, person = context()
    events = []
    async def emit(room, person, text, **kwargs):
        events.append(kwargs)
    def fail(pcm):
        raise RuntimeError("inference failure")
    speech.recognize = fail
    await speech.submit(b"12", room, person, emit, "a")
    await speech.submit(b"34", room, person, emit, "b")
    assert len(events) == 1 and "error" in events[0]
    await asyncio.wait_for(speech.queue.join(), 5)
    speech.recognize = lambda pcm: "recovered"
    await speech.submit(b"56", room, person, emit, "c")
    await asyncio.wait_for(speech.queue.join(), 5)
    assert events[-1] == {"at": "c"}
    await speech.close()


async def test_capture_flushes_on_minutes_off_and_silence_is_not_queued():
    class Tone(AudioStreamTrack):
        async def recv(self):
            frame = await super().recv()
            for plane in frame.planes:
                plane.update(b"\x10\x27" * (plane.buffer_size // 2))
            return frame
    speech = WhisperSpeechService("", model=object())
    captured = []
    speech.recognize = lambda pcm: captured.append(pcm) or ""
    room, person = context()
    async def emit(*args, **kwargs):
        pass
    task = asyncio.create_task(speech.transcribe(Tone(), room, person, emit))
    await asyncio.sleep(.15)
    assert speech.outstanding(room) == 1
    room.set_minutes("p", False, True)
    await asyncio.sleep(.15)
    await speech.queue.join()
    assert len(captured) == 1 and speech.outstanding(room) == 0
    task.cancel()
    await task
    room.set_minutes("p", True, True)
    task = asyncio.create_task(speech.transcribe(AudioStreamTrack(), room, person, emit))
    await asyncio.sleep(.15)
    task.cancel()
    await task
    assert len(captured) == 1 and speech.outstanding(room) == 0
    await speech.close()


def test_delayed_entries_sorted_by_capture_time():
    store = Store(":memory:")
    room, person = context()
    store.add_room(room)
    store.add_entry(room, person.id, person.name, "later", at="2026-10-17T02:00:00+00:00")
    store.add_entry(room, person.id, person.name, "earlier", at="2026-10-17T01:00:00+00:00")
    assert [e["text"] for e in store.entries(room.id)] == ["earlier", "later"]
    store.db.close()


def test_export_waits_for_pending_transcription(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    speech = WhisperSpeechService("", model=object())
    with TestClient(create_app(str(tmp_path / "minutes.db"), speech, approval_required=False)) as client:
        credentials = client.post("/api/rooms", json={"title": "Meeting", "name": "Host"}).json()
        rid = credentials["room_id"]
        headers = {"Authorization": "Bearer " + credentials["token"]}
        speech.buffered[rid] = 1
        assert client.get(f"/api/rooms/{rid}/minutes", headers=headers).status_code == 409
        speech.buffered.clear()
        assert client.get(f"/api/rooms/{rid}/minutes", headers=headers).status_code == 200
