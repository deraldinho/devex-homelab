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
    def __init__(self, capture, stt, gate, interaction, tts, *, vad=None, transcript_filter=None):
        self._capture = capture
        self._stt = stt
        self._gate = gate
        self._interaction = interaction
        self._tts = tts
        self._vad = vad
        self._transcript_filter = transcript_filter

    def run_once(self) -> VoiceRunResult:
        audio = self._capture.capture_utterance()
        if not audio:
            return VoiceRunResult(VoiceState.LISTENING, "no_speech")
        if self._vad is not None and not self._vad.has_speech(audio):
            return VoiceRunResult(VoiceState.LISTENING, "no_speech")
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
            self._tts.speak(response)
        return VoiceRunResult(VoiceState.LISTENING)
