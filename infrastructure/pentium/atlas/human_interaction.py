from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from .stimulus_model import Stimulus, StimulusSeverity


class HumanInteractionGateway:
    def __init__(self, cognitive_loop, *, context_provider, max_text_chars: int = 256):
        if max_text_chars <= 0:
            raise ValueError("max_text_chars must be > 0")
        self._loop = cognitive_loop
        self._context_provider = context_provider
        self._max_text_chars = int(max_text_chars)

    def handle(self, text: str) -> str | None:
        clean = str(text).strip()
        if not clean:
            return None
        if len(clean) > self._max_text_chars:
            raise ValueError("human interaction exceeds max_text_chars")
        now = datetime.now(timezone.utc).isoformat()
        fingerprint = hashlib.sha256(clean.encode("utf-8")).hexdigest()
        stimulus = Stimulus(
            stimulus_id=f"human-{fingerprint[:16]}", source="human.voice",
            kind="human_interaction", severity=StimulusSeverity.INFO,
            timestamp=now, payload={"text": clean}, novelty=1.0,
            correlation_id=f"human-{fingerprint[:16]}",
        )
        context = dict(self._context_provider())
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
