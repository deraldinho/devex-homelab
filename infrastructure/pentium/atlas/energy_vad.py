from __future__ import annotations

import io
import math
import struct
import wave


class EnergyVad:
    def __init__(self, *, rms_threshold: int = 250, max_samples: int = 160000):
        if rms_threshold <= 0 or max_samples <= 0:
            raise ValueError("VAD bounds invalidos")
        self._threshold = int(rms_threshold)
        self._max_samples = int(max_samples)

    def has_speech(self, audio: bytes) -> bool:
        try:
            with wave.open(io.BytesIO(audio), "rb") as wav:
                if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                    return False
                count = wav.getnframes()
                if count <= 0 or count > self._max_samples:
                    return False
                frames = wav.readframes(count)
        except (wave.Error, EOFError):
            return False
        if len(frames) != count * 2:
            return False
        total = 0
        for (sample,) in struct.iter_unpack("<h", frames):
            total += sample * sample
        rms = math.sqrt(total / count)
        return rms >= self._threshold
