from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class WakePhraseResult:
    activated: bool
    command_text: str | None


class WakePhraseGate:
    def __init__(self, wake_phrase: str, *, max_text_chars: int):
        phrase = wake_phrase.strip()
        if not phrase or max_text_chars <= 0:
            raise ValueError("wake phrase e max_text_chars devem ser validos")
        self._wake_phrase = phrase
        self._max_text_chars = int(max_text_chars)

    def evaluate(self, transcript: str) -> WakePhraseResult:
        if len(transcript) > self._max_text_chars:
            raise ValueError("transcricao excede max_text_chars")
        text = transcript.strip()
        pattern = rf"^{re.escape(self._wake_phrase)}\b[\s,.:;!?-]*"
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if match is None:
            return WakePhraseResult(False, None)
        command = text[match.end():].strip()
        return WakePhraseResult(True, command or None)
