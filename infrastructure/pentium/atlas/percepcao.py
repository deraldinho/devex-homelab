from __future__ import annotations

from dataclasses import dataclass

from .modelo_percepcao import (
    EstadoObservacao,
    EstadoPercepcao,
    EvidenciaPercepcao,
    ResultadoEvidencia,
)


@dataclass(frozen=True)
class PoliticaConfirmacaoPercepcao:
    min_fontes_indisponiveis: int
    confianca_conclusiva: float
    max_evidencias: int

    def __post_init__(self) -> None:
        if self.min_fontes_indisponiveis <= 0:
            raise ValueError("min_fontes_indisponiveis deve ser > 0")
        if not 0.0 <= self.confianca_conclusiva <= 1.0:
            raise ValueError("confianca_conclusiva deve estar entre 0 e 1")
        if self.max_evidencias <= 0:
            raise ValueError("max_evidencias deve ser > 0")


def consolidar_percepcao(entidade_id: str, evidencias, politica: PoliticaConfirmacaoPercepcao, agora: str) -> EstadoPercepcao:
    recentes = tuple(sorted(evidencias, key=lambda ev: (ev.observado_em, ev.evidencia_id))[-politica.max_evidencias :])
    if not recentes:
        return EstadoPercepcao(entidade_id, EstadoObservacao.DESCONHECIDO, 0.0, None, (), (), False, agora)

    disponiveis = tuple(sorted({ev.fonte for ev in recentes if ev.resultado is ResultadoEvidencia.DISPONIVEL}))
    indisponiveis = tuple(sorted({ev.fonte for ev in recentes if ev.resultado is ResultadoEvidencia.INDISPONIVEL}))
    fontes_falhas = tuple(sorted({ev.fonte for ev in recentes if ev.resultado is ResultadoEvidencia.FONTE_INDISPONIVEL}))
    conflito = bool(disponiveis and indisponiveis)
    conclusiva_indisponivel = any(
        ev.resultado is ResultadoEvidencia.INDISPONIVEL and ev.conclusiva and ev.confianca >= politica.confianca_conclusiva
        for ev in recentes
    )

    if conclusiva_indisponivel or len(indisponiveis) >= politica.min_fontes_indisponiveis:
        estado = EstadoObservacao.INACESSIVEL
    elif conflito or indisponiveis or fontes_falhas:
        estado = EstadoObservacao.PARCIALMENTE_OBSERVADO
    elif disponiveis:
        estado = EstadoObservacao.OBSERVADO
    else:
        estado = EstadoObservacao.DESCONHECIDO

    ultima_valida = None
    observacoes_validas = [ev.observado_em for ev in recentes if ev.resultado is ResultadoEvidencia.DISPONIVEL]
    if observacoes_validas:
        ultima_valida = max(observacoes_validas)

    confianca = max((ev.confianca for ev in recentes), default=0.0)
    return EstadoPercepcao(
        entidade_id=entidade_id,
        estado=estado,
        confianca=confianca,
        ultima_observacao_valida=ultima_valida,
        fontes_disponiveis=disponiveis,
        fontes_indisponiveis=tuple(sorted(set(indisponiveis) | set(fontes_falhas))),
        conflito_evidencias=conflito,
        atualizado_em=agora,
    )
