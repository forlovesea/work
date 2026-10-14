from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from aiortc import MediaStreamTrack
from aiortc.mediastreams import MediaStreamError
from av import AudioFrame, AudioResampler

log = logging.getLogger(__name__)


def windows_available_commit():
    """Return remaining system commit in bytes, or None on other platforms."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
            (name, ctypes.c_ulonglong) for name in (
                "total_physical", "available_physical", "total_pagefile",
                "available_pagefile", "total_virtual", "available_virtual", "extended"
            )
        ]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return status.available_pagefile
    return None


class AudioGate(MediaStreamTrack):
    kind = "audio"

    def __init__(self, source, allowed):
        super().__init__()
        self.source, self.allowed = source, allowed

    async def recv(self):
        frame = await self.source.recv()
        if self.allowed():
            return frame
        silent = AudioFrame(format=frame.format.name, layout=frame.layout.name, samples=frame.samples)
        silent.sample_rate, silent.pts, silent.time_base = frame.sample_rate, frame.pts, frame.time_base
        for plane in silent.planes:
            plane.update(bytes(plane.buffer_size))
        return silent

    def stop(self):
        super().stop()
        self.source.stop()


class SpeechService:
    def __init__(self, model_path: str):
        self.model = None
        self.error = "한국어 음성 인식 모델이 설치되지 않았습니다. 서버 관리자에게 문의하세요."
        if model_path and Path(model_path).is_dir():
            try:
                from vosk import Model
                # Vosk's Windows native library cannot open some Unicode absolute
                # paths. A relative ASCII path works when launched from this project.
                native_path = model_path
                if os.name == "nt":
                    relative = os.path.relpath(model_path)
                    if relative.isascii():
                        native_path = relative
                self.model = Model(native_path)
                self.error = ""
            except Exception:
                log.exception("Cannot load Vosk model")
                self.error = "음성 인식 모델을 불러오지 못했습니다. 서버 로그를 확인하세요."
                available = windows_available_commit()
                if available is not None and available < 512 * 1024 * 1024:
                    log.error("Windows available commit is only %.0f MiB", available / 1024 / 1024)
                    self.error = (
                        "서버의 메모리 할당 여유가 부족하여 음성 인식 모델을 불러오지 못했습니다. "
                        "사용하지 않는 앱을 종료하거나 Windows 가상 메모리 설정을 확인한 뒤 "
                        "서버를 다시 시작하세요."
                    )

    @property
    def available(self):
        return self.model is not None

    async def transcribe(self, track, room, participant, emit):
        """Drain audio continuously. Reset recognition at each floor/recording boundary."""
        from vosk import KaldiRecognizer
        recognizer = None
        epoch = None
        resampler = AudioResampler(format="s16", layout="mono", rate=16000)
        pending = bytearray()

        async def blocking(fn, *args):
            # Cancellation must not run FinalResult concurrently with AcceptWaveform.
            job = asyncio.create_task(asyncio.to_thread(fn, *args))
            try:
                return await asyncio.shield(job)
            except asyncio.CancelledError:
                await job
                raise

        async def result(final=False):
            if recognizer is None:
                return
            raw = await blocking(recognizer.FinalResult if final else recognizer.Result)
            text = json.loads(raw).get("text", "").strip()
            if text:
                await emit(room, participant, text)

        async def flush():
            if recognizer is not None:
                if pending:
                    await blocking(recognizer.AcceptWaveform, bytes(pending))
                    pending.clear()
                await result(final=True)

        try:
            while True:
                frame = await track.recv()
                permitted = room.minutes_enabled and room.can_speak(participant.id)
                current = room.epoch if permitted else None
                if current != epoch:
                    await flush()
                    pending.clear()
                    recognizer = KaldiRecognizer(self.model, 16000) if permitted else None
                    resampler = AudioResampler(format="s16", layout="mono", rate=16000)
                    epoch = current
                if recognizer is None:
                    continue
                for audio in resampler.resample(frame):
                    pending.extend(audio.to_ndarray().tobytes())
                if len(pending) >= 6400:
                    data = bytes(pending)
                    pending.clear()
                    if await blocking(recognizer.AcceptWaveform, data):
                        await result()
        except (MediaStreamError, asyncio.CancelledError):
            await flush()
        except Exception:
            log.exception("Speech recognition stopped")
            await emit(room, participant, "", error="음성 인식 오류가 발생했습니다. 재입장 후 다시 시도하세요.")
        finally:
            track.stop()
