from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


class SubprocessWhisperRunner:
    def __init__(self, *, temp_dir: str | Path | None = None, executor=subprocess.run):
        self._temp_dir = Path(temp_dir) if temp_dir is not None else None
        self._executor = executor

    def run(self, argv, *, input_bytes: bytes, timeout_s: float, max_output_bytes: int) -> str:
        if self._temp_dir is not None:
            self._temp_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(self._temp_dir, 0o700)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=self._temp_dir) as tmp:
            tmp.write(input_bytes)
            wav_path = tmp.name
        try:
            completed = self._executor(
                [*argv, wav_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_s,
                check=True,
                shell=False,
            )
            data = completed.stdout[:max_output_bytes]
            return data.decode("utf-8", errors="replace")
        finally:
            try:
                os.unlink(wav_path)
            except FileNotFoundError:
                pass


class WhisperSttBackend:
    def __init__(self, binary: str, model: str, *, runner=None, max_audio_bytes=1_000_000, timeout_s=30.0, max_output_bytes=4096):
        self._binary = binary
        self._model = model
        self._runner = runner or SubprocessWhisperRunner()
        self._max_audio_bytes = max_audio_bytes
        self._timeout_s = timeout_s
        self._max_output_bytes = max_output_bytes

    def transcribe(self, audio: bytes) -> str:
        if len(audio) > self._max_audio_bytes:
            raise ValueError("audio exceeds max_audio_bytes")
        argv = [self._binary, "-m", self._model, "-l", "pt", "--no-timestamps", "-nt", "-np"]
        text = self._runner.run(argv, input_bytes=audio, timeout_s=self._timeout_s, max_output_bytes=self._max_output_bytes)
        return text.strip()
