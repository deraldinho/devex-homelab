from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .modelo_contexto_cognitivo import MotivoAtivacaoCognitiva


@dataclass(frozen=True)
class RespostaCognitiva:
    ativado: bool
    motivo: str | None
    texto: str | None
    razao: str | None
    backend: str | None
    duracao_ms: int | None


class ReactionLoopCognitivo:
    def __init__(self, policy, builder, gateway):
        self._policy = policy
        self._builder = builder
        self._gateway = gateway
    def processar(self, *, fingerprint: str, agora: str,
                 sinais_ativacao: Mapping[str, Any], dados_contexto: Mapping[str, Any]) -> RespostaCognitiva:
        decisao = self._policy.avaliar(
            fingerprint=fingerprint,
            agora=agora,
            **dict(sinais_ativacao),
        )
        if not decisao.ativar:
            return RespostaCognitiva(
                False, None, None, decisao.razao_bloqueio, None, None
            )

        motivo = decisao.motivo
        contexto = self._builder.construir(
            motivo=motivo,
            agora=agora,
            **dict(dados_contexto),
        )
        autonomo = motivo is not MotivoAtivacaoCognitiva.INTERACAO_HUMANA
        self._policy.registrar_ativacao(fingerprint, agora, autonomo)
        resultado = self._gateway.inferir(contexto, "formular_resposta_cognitiva")

        if not resultado.sucesso:
            return RespostaCognitiva(
                True,
                motivo.value if motivo is not None else None,
                None,
                "llm_indisponivel",
                resultado.backend,
                resultado.duracao_ms,
            )

        return RespostaCognitiva(
            True,
            motivo.value if motivo is not None else None,
            resultado.texto,
            None,
            resultado.backend,
            resultado.duracao_ms,
        )
