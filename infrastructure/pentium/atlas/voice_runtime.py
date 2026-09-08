from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from .modelo_visual_atlas import EstadoInteracaoVisual


class VoiceState(str, Enum):
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    DEGRADED = "DEGRADED"
    MUTED = "MUTED"


@dataclass(frozen=True)
class VoiceRunResult:
    state: VoiceState
    reason: str | None = None


class VoiceRuntime:
    def __init__(
        self,
        capture,
        stt,
        gate,
        interaction,
        tts,
        *,
        vad=None,
        transcript_filter=None,
        visual_state_sink=None,
        now=lambda: datetime.now(timezone.utc),
    ):
        self._capture = capture
        self._stt = stt
        self._gate = gate
        self._interaction = interaction
        self._tts = tts
        self._vad = vad
        self._transcript_filter = transcript_filter
        self._visual_state_sink = visual_state_sink
        self._now = now

    def _emit_visual(self, **flags) -> None:
        if self._visual_state_sink is None:
            return
        try:
            self._visual_state_sink(
                EstadoInteracaoVisual(
                    atualizado_em=self._now().astimezone(timezone.utc).isoformat(),
                    **flags,
                )
            )
        except Exception:
            return

    def run_once(self) -> VoiceRunResult:
        self._emit_visual(ouvindo=True)
        try:
            audio = self._capture.capture_utterance()
            if not audio:
                return VoiceRunResult(VoiceState.LISTENING, "no_speech")
            if self._vad is not None and not self._vad.has_speech(audio):
                return VoiceRunResult(VoiceState.LISTENING, "no_speech")

            self._emit_visual(pensando=True)
            transcript = self._stt.transcribe(audio)
            if self._transcript_filter is not None:
                transcript = self._transcript_filter.clean(transcript)
                if not transcript:
                    return VoiceRunResult(VoiceState.LISTENING, "non_speech_transcript")
            decision = self._gate.evaluate(transcript)
            if not decision.activated or not decision.command_text:
                return VoiceRunResult(VoiceState.LISTENING, "wake_phrase_missing")
            response = self._interaction.handle(decision.command_text)
            if response:
                self._emit_visual(falando=True)
                self._tts.speak(response)
            return VoiceRunResult(VoiceState.LISTENING)
        finally:
            self._emit_visual(ouvindo=True)
