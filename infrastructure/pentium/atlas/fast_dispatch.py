from __future__ import annotations

from typing import Protocol

from .modelo_evento_semantico import EventoSemantico
from .modelo_fast_dispatch import (
    EstadoLaneDispatch,
    ResultadoFastDispatch,
    ResultadoLaneDispatch,
)
from .modelo_fast_router import DecisaoFastRouter, RotaSemantica


class PortaFastReaction(Protocol):
    def reagir(self, evento: EventoSemantico) -> str: ...


class PortaAffect(Protocol):
    def aplicar(self, evento: EventoSemantico) -> str: ...


class PortaCacheLookup(Protocol):
    def consultar(self, evento: EventoSemantico) -> str: ...


class PortaSlowLlm(Protocol):
    def defer(self, evento: EventoSemantico) -> str: ...

class FastDispatcher:
    def __init__(
        self,
        *,
        fast_reaction: PortaFastReaction | None = None,
        affect: PortaAffect | None = None,
        cache_lookup: PortaCacheLookup | None = None,
        slow_llm: PortaSlowLlm | None = None,
    ):
        self._fast_reaction = fast_reaction
        self._affect = affect
        self._cache_lookup = cache_lookup
        self._slow_llm = slow_llm

    @staticmethod
    def _falha(rota: RotaSemantica, detalhe: str) -> ResultadoLaneDispatch:
        return ResultadoLaneDispatch(rota, EstadoLaneDispatch.FAILED, detalhe)

    def dispatch(self, evento: EventoSemantico, decisao: DecisaoFastRouter) -> ResultadoFastDispatch:
        if decisao.rotas == (RotaSemantica.DROP,):
            return ResultadoFastDispatch(decisao.rotas, ())

        resultados: list[ResultadoLaneDispatch] = []
        for rota in decisao.rotas:
            resultados.append(self._dispatch_lane(rota, evento))
        return ResultadoFastDispatch(decisao.rotas, tuple(resultados))

    def _dispatch_lane(self, rota: RotaSemantica, evento: EventoSemantico) -> ResultadoLaneDispatch:
        try:
            if rota is RotaSemantica.FAST_REACTION:
                if self._fast_reaction is None:
                    return self._falha(rota, "porta_indisponivel:fast_reaction")
                detalhe = self._fast_reaction.reagir(evento)
                return ResultadoLaneDispatch(rota, EstadoLaneDispatch.DELIVERED, detalhe)

            if rota is RotaSemantica.AFFECT:
                if self._affect is None:
                    return self._falha(rota, "porta_indisponivel:affect")
                detalhe = self._affect.aplicar(evento)
                return ResultadoLaneDispatch(rota, EstadoLaneDispatch.DELIVERED, detalhe)

            if rota is RotaSemantica.CACHE_LOOKUP:
                if self._cache_lookup is None:
                    return self._falha(rota, "porta_indisponivel:cache_lookup")
                detalhe = self._cache_lookup.consultar(evento)
                return ResultadoLaneDispatch(rota, EstadoLaneDispatch.DELIVERED, detalhe)

            if rota is RotaSemantica.SLOW_LLM:
                if self._slow_llm is None:
                    return self._falha(rota, "porta_indisponivel:slow_llm")
                detalhe = self._slow_llm.defer(evento)
                return ResultadoLaneDispatch(rota, EstadoLaneDispatch.DEFERRED, detalhe)

            return self._falha(rota, "rota_nao_suportada")
        except Exception as exc:
            nome = exc.__class__.__name__[:96]
            return self._falha(rota, f"erro:{nome}")
