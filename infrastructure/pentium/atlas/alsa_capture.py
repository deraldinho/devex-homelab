from __future__ import annotations

import subprocess


class SubprocessArecordRunner:
    def run(self, argv, *, timeout_s: float, max_output_bytes: int) -> bytes:
        completed = subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
            check=True,
            shell=False,
        )
        if len(completed.stdout) > max_output_bytes:
            raise ValueError("captured audio exceeds max_output_bytes")
        return completed.stdout


class AlsaCaptureBackend:
    def __init__(self, binary: str, *, runner=None, device="plughw:0,0", duration_s=4, max_audio_bytes=256000):
        if duration_s < 1 or duration_s > 10:
            raise ValueError("duration_s must be between 1 and 10")
        self._binary = binary
        self._runner = runner or SubprocessArecordRunner()
        self._device = device
        self._duration_s = duration_s
        self._max_audio_bytes = max_audio_bytes

    def capture_utterance(self) -> bytes:
        argv = [self._binary, "-D", self._device, "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", str(self._duration_s), "-t", "wav", "-"]
        return self._runner.run(argv, timeout_s=self._duration_s + 2, max_output_bytes=self._max_audio_bytes)
