from __future__ import annotations

import struct


class NlmsCanceller:
    def __init__(self, *, taps: int = 16, mu: float = 0.3, epsilon: float = 1.0):
        if taps <= 0 or not 0 < mu <= 1 or epsilon <= 0:
            raise ValueError("invalid NLMS parameters")
        self._taps = int(taps)
        self._mu = float(mu)
        self._epsilon = float(epsilon)
        self._weights = [0.0] * self._taps
        self._history = [0.0] * self._taps

    def process_sample(self, primary: int, reference: int, *, adapt: bool = True) -> int:
        self._history = [float(reference)] + self._history[:-1]
        estimated = sum(w * x for w, x in zip(self._weights, self._history))
        error = float(primary) - estimated
        if adapt:
            norm = self._epsilon + sum(x * x for x in self._history)
            scale = self._mu * error / norm
            self._weights = [w + scale * x for w, x in zip(self._weights, self._history)]
        return max(-32768, min(32767, int(round(error))))

class AdaptiveNoiseCancelledFrameSource:
    def __init__(self, source, *, primary_channel='left', reference_channel='right', taps=16, mu=0.3, calibration_frames=50):
        if primary_channel == reference_channel or {primary_channel, reference_channel} != {'left', 'right'}:
            raise ValueError('channels must be left/right and distinct')
        if calibration_frames < 0:
            raise ValueError('calibration_frames must be >= 0')
        self._source = source
        self._primary_left = primary_channel == 'left'
        self._canceller = NlmsCanceller(taps=taps, mu=mu)
        self._calibration_frames = int(calibration_frames)
        self._frames_seen = 0

    def read_frame(self) -> bytes:
        frame = self._source.read_frame()
        if not frame:
            return b''
        if len(frame) % 4:
            raise ValueError('stereo PCM frame must be 16-bit interleaved')
        adapt = self._frames_seen < self._calibration_frames
        out = bytearray()
        for left, right in struct.iter_unpack('<hh', frame):
            primary, reference = (left, right) if self._primary_left else (right, left)
            clean = self._canceller.process_sample(primary, reference, adapt=adapt)
            out.extend(struct.pack('<h', clean))
        self._frames_seen += 1
        return bytes(out)

    def close(self) -> None:
        self._source.close()
