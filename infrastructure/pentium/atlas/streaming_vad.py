from __future__ import annotations

import math
import statistics
import struct
from collections import deque


class StreamingAdaptiveVad:
    def __init__(self, *, calibration_frames=50, history_frames=200,
                 min_rms_threshold=220, snr_ratio=1.15, margin=150):
        if calibration_frames < 1 or history_frames < calibration_frames:
            raise ValueError("streaming VAD history bounds invalid")
        if min_rms_threshold <= 0 or snr_ratio <= 1 or margin < 0:
            raise ValueError("streaming VAD threshold bounds invalid")
        self._remaining = int(calibration_frames)
        self._history = deque(maxlen=int(history_frames))
        self._minimum = float(min_rms_threshold)
        self._ratio = float(snr_ratio)
        self._margin = float(margin)

    @property
    def history_size(self):
        return len(self._history)

    @staticmethod
    def _rms(frame: bytes) -> float:
        if not frame or len(frame) % 2:
            return 0.0
        samples = [x[0] for x in struct.iter_unpack('<h', frame)]
        return math.sqrt(sum(v*v for v in samples) / len(samples))

    def _threshold(self) -> float:
        if not self._history:
            return self._minimum
        ordered = sorted(self._history)
        median = float(statistics.median(ordered))
        peak = float(ordered[min(len(ordered) - 1, int((len(ordered) - 1) * 0.99))])
        return max(self._minimum, median * self._ratio + self._margin, peak + self._margin)

    def is_speech_frame(self, frame: bytes) -> bool:
        rms = self._rms(frame)
        if rms <= 0:
            return False
        if self._remaining > 0:
            self._history.append(rms)
            self._remaining -= 1
            return False
        speech = rms >= self._threshold()
        if not speech:
            self._history.append(rms)
        return speech
