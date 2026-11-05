"""Exercise real 48 kHz resampling without downloading recognition models."""
import json
from fractions import Fraction
from types import SimpleNamespace

import pytest
from av import AudioFrame
from aiortc.mediastreams import MediaStreamError

from app.media import SpeechService
from app.whisper_speech import WhisperSpeechService
from test_whisper_speech import context


class ShortTrack:
    def __init__(self, room, boundary):
        self.room, self.boundary = room, boundary
        self.count = 0
        self.stopped = False

    async def recv(self):
        self.count += 1
        if self.count == 2 and self.boundary:
            self.room.set_minutes("p", False, True)
        elif self.count > 1:
            raise MediaStreamError
        frame = AudioFrame(format="s16", layout="mono", samples=960)
        frame.sample_rate = 48000
        frame.time_base = Fraction(1, 48000)
        frame.pts = (self.count - 1) * 960
        frame.planes[0].update(b"\x10\x27" * 960)
        return frame

    def stop(self):
        self.stopped = True


@pytest.mark.parametrize("engine", ["vosk", "whisper"])
@pytest.mark.parametrize("boundary", [False, True])
async def test_short_utterance_preserves_resampler_tail(monkeypatch, engine, boundary):
    room, person = context()
    captured, events = [], []

    class Recognizer:
        def AcceptWaveform(self, pcm):
            captured.append(pcm)
            return True

        def Result(self):
            return json.dumps({"text": "short utterance"})

        def FinalResult(self):
            return json.dumps({"text": ""})

    async def emit(room, person, text, **kwargs):
        assert "error" not in kwargs
        events.append(text)

    if engine == "vosk":
        import vosk
        monkeypatch.setattr(vosk, "KaldiRecognizer", lambda *args: Recognizer())
        service = SpeechService("")
    else:
        service = WhisperSpeechService("", model=object())
        service.recognize = lambda pcm: captured.append(pcm) or "short utterance"
    track = ShortTrack(room, boundary)
    await service.transcribe(track, room, person, emit)
    if engine == "whisper":
        await service.queue.join()
        assert service.outstanding(room) == 0
        await service.close()
    assert sum(len(pcm) for pcm in captured) == 320 * 2
    assert events == ["short utterance"]
    assert track.stopped


async def test_whisper_rejects_repetition_and_invalid_scores():
    segments = [SimpleNamespace(text=text, avg_logprob=prob,
                               no_speech_prob=0.1, compression_ratio=ratio)
                for text, prob, ratio in [
                    ("valid", -0.2, 1.2), ("repeated", -0.2, 3.5),
                    ("invalid", float("inf"), 1.2),
                    ("invalid ratio", -0.2, float("nan"))]]
    model = SimpleNamespace(transcribe=lambda *args, **kwargs: (iter(segments), None))
    service = WhisperSpeechService("", model=model)
    try:
        assert service.recognize(b"\x00\x01" * 16000) == "valid"
    finally:
        await service.close()
