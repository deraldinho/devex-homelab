from __future__ import annotations

from .modelo_contexto_cognitivo import MotivoAtivacaoCognitiva


class ReasoningPolicy:
    _ON_TERMS = ("analise", "analisa", "por que", "causa", "diagnost", "planej", "correlac", "investig")
    _AUTO_TERMS = ("estranho", "instavel", "lento", "problema", "falha", "x99", "pentium", "rede")

    def select(self, contexto, tarefa: str) -> str:
        motivo = getattr(contexto, "motivo_ativacao", None)
        if motivo in {
            MotivoAtivacaoCognitiva.CRITICIDADE_TECNICA,
            MotivoAtivacaoCognitiva.EXPECTATIVA_QUEBRADA,
        }:
            return "on"

        text = self._human_text(contexto).lower()
        if any(term in text for term in self._ON_TERMS):
            return "on"
        if any(term in text for term in self._AUTO_TERMS):
            return "auto"
        return "off"

    @staticmethod
    def _human_text(contexto) -> str:
        for item in reversed(tuple(getattr(contexto, "mudancas_recentes", ()) or ())):
            if item.get("kind") == "human_interaction":
                payload = item.get("payload") or {}
                return str(payload.get("text") or "")
        return ""
