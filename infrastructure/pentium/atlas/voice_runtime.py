from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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
    def __init__(self, capture, stt, gate, interaction, tts):
        self._capture = capture
        self._stt = stt
        self._gate = gate
        self._interaction = interaction
        self._tts = tts

    def run_once(self) -> VoiceRunResult:
        audio = self._capture.capture_utterance()
        transcript = self._stt.transcribe(audio)
        decision = self._gate.evaluate(transcript)
        if not decision.activated or not decision.command_text:
            return VoiceRunResult(VoiceState.LISTENING, "wake_phrase_missing")
        response = self._interaction.handle(decision.command_text)
        if response:
            self._tts.speak(response)
        return VoiceRunResult(VoiceState.LISTENING)
