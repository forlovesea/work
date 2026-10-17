"""Bounded, delayed Korean transcription; audio stays in memory, never on disk."""
from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from av import AudioResampler
from aiortc.mediastreams import MediaStreamError

log = logging.getLogger(__name__)


class WhisperSpeechService:
    engine = "faster-whisper"

    def __init__(self, model_path, *, model=None, chunk_seconds=20, queue_size=60):
        self.model = model
        self.error = "Whisper 모델 또는 패키지가 없습니다. 설치 안내를 확인하세요."
        self.chunk_samples = int(chunk_seconds * 16000)
        self.queue = asyncio.Queue(maxsize=queue_size)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="speech")
        self.pending = defaultdict(int)
        self.buffered = defaultdict(int)
        self.worker = None
        self.on_status = None
        self.prompt = os.getenv("WHISPER_PROMPT", "")[:1000]
        if model is None and Path(model_path).is_dir() and importlib.util.find_spec("faster_whisper"):
            try:
                from faster_whisper import WhisperModel
                self.model = WhisperModel(
                    model_path, device="cpu", compute_type="int8", cpu_threads=1,
                    num_workers=1, local_files_only=True,
                )
            except Exception:
                log.exception("Cannot load Whisper model")
        if self.model is not None:
            self.error = ""

    @property
    def available(self):
        return self.model is not None

    def outstanding(self, room):
        return self.pending.get(room.id, 0) + self.buffered.get(room.id, 0)

    async def status(self, room):
        if self.on_status:
            try:
                await self.on_status(room, self.outstanding(room))
            except Exception:
                log.exception("Cannot broadcast speech status")

    def recognize(self, pcm):
        audio = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
        segments, _ = self.model.transcribe(
            audio, language="ko", task="transcribe", beam_size=5,
            temperature=0.0, condition_on_previous_text=False,
            initial_prompt=self.prompt or None,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 600, "speech_pad_ms": 300},
            no_speech_threshold=0.6, log_prob_threshold=-1.0,
            compression_ratio_threshold=2.4,
        )
        # Consume the lazy generator on the inference thread, not the event loop.
        return " ".join(s.text.strip() for s in segments
                        if s.text.strip() and s.avg_logprob >= -1.0 and s.no_speech_prob < 0.6)

    async def submit(self, pcm, room, participant, emit, at):
        if not pcm:
            return
        try:
            self.queue.put_nowait((pcm, room, participant, emit, at))
        except asyncio.QueueFull:
            await emit(room, participant, "", error="음성 인식 대기열이 가득 차 이번 발화가 기록되지 않았습니다. 자동 기록을 잠시 꺼 주세요.")
            return
        self.pending[room.id] += 1
        if self.worker is None:
            self.worker = asyncio.create_task(self.work())
        await self.status(room)

    async def work(self):
        while True:
            pcm, room, person, emit, at = await self.queue.get()
            try:
                text = await asyncio.get_running_loop().run_in_executor(self.executor, self.recognize, pcm)
                if text:
                    await emit(room, person, text, at=at)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Whisper transcription failed")
                try:
                    await emit(room, person, "", error="음성 인식 처리에 실패하여 일부 발화가 기록되지 않았습니다. 서버 로그를 확인하세요.")
                except Exception:
                    log.exception("Cannot report transcription failure")
            finally:
                self.pending[room.id] -= 1
                if not self.pending[room.id]:
                    del self.pending[room.id]
                self.queue.task_done()
                await self.status(room)

    async def close(self):
        # Operations guide requires draining before restarting; bound shutdown time.
        try:
            await asyncio.wait_for(self.queue.join(), timeout=25)
        except asyncio.TimeoutError:
            log.error("Shutdown with unfinished transcription; pending audio will be lost")
        if self.worker:
            self.worker.cancel()
            await asyncio.gather(self.worker, return_exceptions=True)
        self.executor.shutdown(wait=False, cancel_futures=True)

    async def transcribe(self, track, room, participant, emit):
        buffer = bytearray()
        preroll = bytearray()
        quiet = 0
        epoch = None
        at = None
        resampler = AudioResampler(format="s16", layout="mono", rate=16000)

        async def flush():
            nonlocal quiet, at
            if buffer:
                pcm = bytes(buffer)
                buffer.clear()
                self.buffered[room.id] -= 1
                if not self.buffered[room.id]:
                    del self.buffered[room.id]
                await self.submit(pcm, room, participant, emit, at)
                await self.status(room)
            quiet = 0
            at = None

        try:
            while True:
                frame = await track.recv()
                permitted = room.minutes_enabled and room.can_speak(participant.id)
                current = room.epoch if permitted else None
                if current != epoch:
                    await flush()
                    preroll.clear()
                    resampler = AudioResampler(format="s16", layout="mono", rate=16000)
                    epoch = current
                if not permitted:
                    continue
                for audio in resampler.resample(frame):
                    pcm = audio.to_ndarray().astype("<i2", copy=False).tobytes()
                    values = np.frombuffer(pcm, dtype="<i2").astype(np.float32)
                    # Only reject near-digital-silence here; Silero VAD does speech detection.
                    audible = bool(values.size and np.sqrt(np.mean(values * values)) > 32)
                    if not buffer and not audible:
                        preroll.extend(pcm)
                        del preroll[:-6400]  # 200 ms context before speech onset
                        continue
                    if not buffer:
                        at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                        buffer.extend(preroll)
                        preroll.clear()
                        self.buffered[room.id] += 1
                        await self.status(room)
                    buffer.extend(pcm)
                    quiet = 0 if audible else quiet + len(pcm) // 2
                    if len(buffer) // 2 >= self.chunk_samples or (quiet >= 12800 and len(buffer) >= 96000):
                        await flush()
        except (MediaStreamError, asyncio.CancelledError):
            pass
        except Exception:
            log.exception("Audio capture for Whisper failed")
            await emit(room, participant, "", error="음성 수집이 중단되었습니다. 다시 입장하세요.")
        finally:
            await flush()
            track.stop()
