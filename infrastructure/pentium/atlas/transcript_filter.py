from __future__ import annotations

import re
import unicodedata


class NonSpeechTranscriptFilter:
    _NON_SPEECH = {
        "musica de fundo",
        "musica",
        "ruido",
        "silencio",
        "aplausos",
        "risos",
    }

    @staticmethod
    def _normalize(text: str) -> str:
        value = unicodedata.normalize("NFKD", text)
        value = "".join(ch for ch in value if not unicodedata.combining(ch))
        value = value.casefold().strip()
        value = re.sub(r"^[\[\(\{]+|[\]\)\}]+$", "", value).strip()
        value = re.sub(r"[.!?…]+$", "", value).strip()
        return value

    def clean(self, transcript: str) -> str:
        text = transcript.strip()
        if not text:
            return ""
        if self._normalize(text) in self._NON_SPEECH:
            return ""
        return text
