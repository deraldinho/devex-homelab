from __future__ import annotations

from datetime import datetime

from .modelo_afetivo import EstadoAfetivo, PersonalidadeBase, PoliticaDecaimento


def _aproximar(atual: float, base: float, meia_vida_s: float, segundos: float) -> float:
    return base + (atual - base) * (0.5 ** (segundos / meia_vida_s))


def decair_estado(
    estado: EstadoAfetivo,
    personalidade: PersonalidadeBase,
    politica: PoliticaDecaimento,
    agora: str,
    *,
    modo_offline: bool = False,
) -> EstadoAfetivo:
    instante = personalidade.criar_estado(agora).atualizado_em
    decorridos = (
        datetime.fromisoformat(instante) - datetime.fromisoformat(estado.atualizado_em)
    ).total_seconds()
    if decorridos < 0:
        raise ValueError("agora não pode ser anterior ao estado")
    efetivos = (
        min(decorridos, politica.atenuacao_offline_maxima_s)
        if modo_offline
        else decorridos
    )
    return EstadoAfetivo(
        _aproximar(estado.valencia, personalidade.valencia, politica.meia_vida_valencia_s, efetivos),
        _aproximar(estado.ativacao, personalidade.ativacao, politica.meia_vida_ativacao_s, efetivos),
        _aproximar(estado.estresse, personalidade.estresse, politica.meia_vida_estresse_s, efetivos),
        _aproximar(estado.confianca, personalidade.confianca, politica.meia_vida_confianca_s, efetivos),
        _aproximar(estado.engajamento, personalidade.engajamento, politica.meia_vida_engajamento_s, efetivos),
        _aproximar(estado.curiosidade, personalidade.curiosidade, politica.meia_vida_curiosidade_s, efetivos),
        instante,
        estado.foco_atencao,
    )
