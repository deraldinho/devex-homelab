from __future__ import annotations

import io
import math
import statistics
import struct
import wave


class AdaptiveEnergyVad:
    def __init__(self, *, min_rms_threshold: int = 220, snr_ratio: float = 1.15,
                 margin: int = 150, calibration_frames: int = 1, alpha: float = 0.2,
                 frame_ms: int = 20, min_speech_frames: int = 5,
                 max_samples: int = 160000):
        if min_rms_threshold <= 0 or snr_ratio <= 1 or margin < 0:
            raise ValueError("adaptive VAD bounds invalidos")
        if calibration_frames < 0 or not 0 < alpha <= 1 or max_samples <= 0:
            raise ValueError("adaptive VAD calibration invalid")
        if not 10 <= frame_ms <= 100 or min_speech_frames <= 0:
            raise ValueError("adaptive VAD frame bounds invalidos")
        self._minimum = float(min_rms_threshold)
        self._ratio = float(snr_ratio)
        self._margin = float(margin)
        self._remaining = int(calibration_frames)
        self._alpha = float(alpha)
        self._frame_ms = int(frame_ms)
        self._min_speech_frames = int(min_speech_frames)
        self._max_samples = int(max_samples)
        self._noise_floor = self._minimum
        self._noise_peak_floor = self._minimum
        self._observations = 0

    @property
    def noise_floor(self) -> float:
        return self._noise_floor

    @property
    def noise_peak_floor(self) -> float:
        return self._noise_peak_floor

    def _frame_rms(self, audio: bytes) -> list[float] | None:
        try:
            with wave.open(io.BytesIO(audio), "rb") as wav:
                if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                    return None
                count = wav.getnframes()
                rate = wav.getframerate()
                if count <= 0 or count > self._max_samples or rate <= 0:
                    return None
                frames = wav.readframes(count)
        except (wave.Error, EOFError):
            return None
        if len(frames) != count * 2:
            return None
        samples = [sample[0] for sample in struct.iter_unpack("<h", frames)]
        size = max(1, int(rate * self._frame_ms / 1000))
        values = []
        for start in range(0, len(samples) - size + 1, size):
            chunk = samples[start:start + size]
            values.append(math.sqrt(sum(value * value for value in chunk) / len(chunk)))
        return values or None

    def _observe_noise(self, frame_rms: list[float]) -> None:
        baseline = float(statistics.median(frame_rms))
        ordered = sorted(frame_rms)
        peak_index = min(len(ordered) - 1, int((len(ordered) - 1) * 0.99))
        peak = float(ordered[peak_index])
        if self._observations == 0:
            self._noise_floor = max(self._minimum, baseline)
            self._noise_peak_floor = max(self._minimum, peak)
        else:
            self._noise_floor = max(
                self._minimum,
                (1 - self._alpha) * self._noise_floor + self._alpha * baseline,
            )
            self._noise_peak_floor = max(
                self._minimum,
                (1 - self._alpha) * self._noise_peak_floor + self._alpha * peak,
            )
        self._observations += 1

    def has_speech(self, audio: bytes) -> bool:
        values = self._frame_rms(audio)
        if not values:
            return False
        if self._remaining > 0:
            self._observe_noise(values)
            self._remaining -= 1
            return False
        threshold = max(
            self._minimum,
            self._noise_floor * self._ratio + self._margin,
            self._noise_peak_floor + self._margin,
        )
        longest = current = 0
        for rms in values:
            current = current + 1 if rms >= threshold else 0
            longest = max(longest, current)
        if longest >= self._min_speech_frames:
            return True
        self._observe_noise(values)
        return False
