from __future__ import annotations

import io
import wave
from collections import deque


class StreamingUtteranceCapture:
    def __init__(self, source_factory, detector, *, frame_ms=20,
                 start_speech_frames=3, trailing_silence_ms=800,
                 max_utterance_s=12, pre_roll_ms=200, listen_window_s=4):
        if not 10 <= frame_ms <= 100:
            raise ValueError("frame_ms invalid")
        if start_speech_frames <= 0 or trailing_silence_ms < frame_ms:
            raise ValueError("speech segmentation bounds invalid")
        if max_utterance_s <= 0 or pre_roll_ms < 0 or listen_window_s <= 0:
            raise ValueError("utterance bounds invalid")
        self._source_factory = source_factory
        self._detector = detector
        self._frame_ms = int(frame_ms)
        self._start_frames = int(start_speech_frames)
        self._trail_frames = max(1, int(trailing_silence_ms // frame_ms))
        self._max_frames = max(1, int(max_utterance_s * 1000 // frame_ms))
        self._pre_roll_frames = max(0, int(pre_roll_ms // frame_ms))
        self._listen_frames = max(1, int(listen_window_s * 1000 // frame_ms))

    def _wav(self, frames: list[bytes]) -> bytes:
        out = io.BytesIO()
        with wave.open(out, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"".join(frames))
        return out.getvalue()

    def capture_utterance(self) -> bytes:
        source = self._source_factory()
        pre_roll = deque(maxlen=self._pre_roll_frames)
        captured: list[bytes] = []
        speech_run = silence_run = 0
        started = False
        try:
            total_limit = self._listen_frames + self._max_frames
            for index in range(total_limit):
                if not started and index >= self._listen_frames:
                    break
                frame = source.read_frame()
                if not frame:
                    break
                speech = bool(self._detector.is_speech_frame(frame))
                if not started:
                    pre_roll.append(frame)
                    speech_run = speech_run + 1 if speech else 0
                    if speech_run < self._start_frames:
                        continue
                    started = True
                    captured.extend(pre_roll)
                    silence_run = 0
                    continue
                captured.append(frame)
                silence_run = 0 if speech else silence_run + 1
                if silence_run >= self._trail_frames:
                    break
            return self._wav(captured) if captured else b""
        finally:
            source.close()
