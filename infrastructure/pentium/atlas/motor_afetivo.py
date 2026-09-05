from __future__ import annotations

from collections.abc import Callable

from .decaimento_afetivo import decair_estado
from .modelo_afetivo import EstadoAfetivo, ImpulsoAfetivo, PersonalidadeBase, PoliticaDecaimento


class MotorEstadoAfetivo:
    def __init__(
        self,
        personalidade: PersonalidadeBase,
        politica: PoliticaDecaimento,
        estado_inicial: EstadoAfetivo,
        relogio: Callable[[], str],
    ):
        self._personalidade = personalidade
        self._politica = politica
        self._estado = estado_inicial
        self._relogio = relogio

    @property
    def estado_atual(self) -> EstadoAfetivo:
        return self._estado

    def decair_ate(self, agora: str | None = None, *, modo_offline: bool = False) -> EstadoAfetivo:
        instante = agora or self._relogio()
        self._estado = decair_estado(
            self._estado,
            self._personalidade,
            self._politica,
            instante,
            modo_offline=modo_offline,
        )
        return self._estado

    def aplicar_impulso(self, impulso: ImpulsoAfetivo, ocorrido_em: str | None = None) -> EstadoAfetivo:
        instante = ocorrido_em or self._relogio()
        base = self.decair_ate(instante)
        self._estado = EstadoAfetivo(
            base.valencia + impulso.delta_valencia,
            base.ativacao + impulso.delta_ativacao,
            base.estresse + impulso.delta_estresse,
            base.confianca + impulso.delta_confianca,
            base.engajamento + impulso.delta_engajamento,
            base.curiosidade + impulso.delta_curiosidade,
            instante,
            base.foco_atencao,
        )
        return self._estado
