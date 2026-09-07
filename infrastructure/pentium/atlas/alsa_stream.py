from __future__ import annotations

import subprocess


class SubprocessPcmFrameSource:
    def __init__(self, proc, *, frame_bytes: int = 640):
        self._proc = proc
        self._frame_bytes = int(frame_bytes)

    def read_frame(self) -> bytes:
        data = self._proc.stdout.read(self._frame_bytes)
        return data if data else b""

    def close(self) -> None:
        if self._proc is None:
            return
        try:
            self._proc.terminate()
            self._proc.wait(timeout=2)
        finally:
            self._proc = None


def open_arecord_pcm(binary: str, *, device: str, frame_ms: int = 20):
    frame_bytes = 16000 * 2 * int(frame_ms) // 1000
    argv = [binary, "-D", device, "-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "raw", "-"]
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=False)
    if proc.stdout is None:
        raise RuntimeError("arecord stdout unavailable")
    return SubprocessPcmFrameSource(proc, frame_bytes=frame_bytes)
