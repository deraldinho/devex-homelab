from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .modelo_contexto_cognitivo import MotivoAtivacaoCognitiva
from .saida_cognitiva import parse_resposta_llm


@dataclass(frozen=True)
class RespostaCognitiva:
    ativado: bool
    motivo: str | None
    texto: str | None
    razao: str | None
    backend: str | None
    duracao_ms: int | None
    resumo: str | None = None
    intencao: str | None = None
    parametros_intencao: dict[str, object] | None = None
    confianca: float | None = None
    requer_confirmacao: bool = False
    intencao_autorizada: bool = False


class ReactionLoopCognitivo:
    def __init__(self, policy, builder, gateway, *, capability_policy=None):
        self._policy = policy
        self._builder = builder
        self._gateway = gateway
        self._capability_policy = capability_policy
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

        if self._capability_policy is None:
            return RespostaCognitiva(
                True,
                motivo.value if motivo is not None else None,
                resultado.texto,
                None,
                resultado.backend,
                resultado.duracao_ms,
            )

        try:
            estruturada = parse_resposta_llm(resultado.texto or "")
        except ValueError:
            return RespostaCognitiva(
                True,
                motivo.value if motivo is not None else None,
                None,
                "saida_llm_invalida",
                resultado.backend,
                resultado.duracao_ms,
            )

        autorizada = False
        requer_confirmacao = estruturada.requer_confirmacao
        if estruturada.intencao is not None:
            decisao_cap = self._capability_policy.avaliar(
                estruturada.intencao,
                estruturada.parametros_intencao,
            )
            autorizada = decisao_cap.autorizada
            requer_confirmacao = requer_confirmacao or decisao_cap.requer_confirmacao

        return RespostaCognitiva(
            True,
            motivo.value if motivo is not None else None,
            estruturada.texto,
            None,
            resultado.backend,
            resultado.duracao_ms,
            estruturada.resumo,
            estruturada.intencao,
            estruturada.parametros_intencao,
            estruturada.confianca,
            requer_confirmacao,
            autorizada,
        )
