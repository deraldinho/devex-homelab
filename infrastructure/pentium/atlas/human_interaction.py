from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from .human_context import CognitiveContextUnavailable
from .stimulus_model import Stimulus, StimulusSeverity


_ALLOWED_SOURCES = frozenset(("human.voice", "human.cli", "human.dashboard", "human.discord"))


def build_human_stimulus(text: str, *, source: str, stimulus_id: str | None = None,
                         timestamp: str | None = None, max_text_chars: int = 512) -> Stimulus:
    if source not in _ALLOWED_SOURCES:
        raise ValueError("human interaction source is not allowed")
    clean=str(text).strip()
    if not clean:
        raise ValueError("human interaction text is required")
    if len(clean)>int(max_text_chars):
        raise ValueError("human interaction exceeds max_text_chars")
    now=timestamp or datetime.now(timezone.utc).isoformat()
    fingerprint=hashlib.sha256(clean.encode("utf-8")).hexdigest()
    sid=str(stimulus_id or f"human-{fingerprint[:16]}")
    return Stimulus(stimulus_id=sid,source=source,kind="human_interaction",
                    severity=StimulusSeverity.INFO,timestamp=now,payload={"text":clean},
                    novelty=1.0,correlation_id=sid)


class HumanInteractionGateway:
    def __init__(self, cognitive_loop, *, context_provider, max_text_chars: int = 256):
        if max_text_chars <= 0:
            raise ValueError("max_text_chars must be > 0")
        self._loop = cognitive_loop
        self._context_provider = context_provider
        self._max_text_chars = int(max_text_chars)

    def handle(self, text: str, *, source: str = "human.voice") -> str | None:
        if source not in _ALLOWED_SOURCES:
            raise ValueError("human interaction source is not allowed")
        clean = str(text).strip()
        if not clean:
            return None
        if len(clean) > self._max_text_chars:
            raise ValueError("human interaction exceeds max_text_chars")
        stimulus = build_human_stimulus(clean, source=source, max_text_chars=self._max_text_chars)
        now = stimulus.timestamp
        fingerprint = hashlib.sha256(clean.encode("utf-8")).hexdigest()
        try:
            context = dict(self._context_provider())
        except CognitiveContextUnavailable:
            return "Meu contexto observacional esta indisponivel no momento."
        recent = list(context.get("mudancas_recentes", ()))
        recent.append(stimulus)
        context["mudancas_recentes"] = recent
        response = self._loop.processar(
            fingerprint=fingerprint, agora=now,
            sinais_ativacao={"interacao_humana": True}, dados_contexto=context,
        )
        if response.texto:
            return response.texto
        if response.razao == "llm_indisponivel":
            return "Estou ouvindo, mas meu modulo de linguagem esta indisponivel."
        return None
