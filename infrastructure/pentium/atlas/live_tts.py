from __future__ import annotations

import subprocess


class LiveTtsError(RuntimeError):
    pass


class LiveTtsBackend:
    def __init__(self, synth_bin: str, player_bin: str, *, voice: str, device: str,
                 max_text_chars: int, max_audio_bytes: int, timeout_s: float = 15.0,
                 env: dict[str, str] | None = None, runner=subprocess.run):
        if max_text_chars <= 0 or max_audio_bytes <= 0 or timeout_s <= 0:
            raise ValueError("bounds TTS invalidos")
        self._synth_bin = synth_bin
        self._player_bin = player_bin
        self._voice = voice
        self._device = device
        self._max_text_chars = int(max_text_chars)
        self._max_audio_bytes = int(max_audio_bytes)
        self._timeout_s = float(timeout_s)
        self._env = dict(env) if env is not None else None
        self._runner = runner

    def speak(self, text: str) -> None:
        value = text.strip()
        if not value:
            raise ValueError("texto TTS nao pode ser vazio")
        if len(value) > self._max_text_chars:
            raise ValueError("texto TTS excede max_text_chars")
        synth = self._runner([self._synth_bin, "-v", self._voice, "--stdout", value], capture_output=True, check=False, timeout=self._timeout_s, env=self._env)
        audio = synth.stdout or b""
        if synth.returncode != 0 or not audio:
            raise LiveTtsError("sintese TTS falhou")
        if len(audio) > self._max_audio_bytes:
            raise LiveTtsError("audio TTS excede max_audio_bytes")
        play = self._runner([self._player_bin, "-D", self._device, "-"], input=audio, capture_output=True, check=False, timeout=self._timeout_s, env=self._env)
        if play.returncode != 0:
            raise LiveTtsError("playback TTS falhou")
