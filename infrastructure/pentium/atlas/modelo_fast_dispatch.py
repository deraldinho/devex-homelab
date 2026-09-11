from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .modelo_fast_router import RotaSemantica


class EstadoLaneDispatch(str, Enum):
    DELIVERED = "delivered"
    DEFERRED = "deferred"
    FAILED = "failed"


@dataclass(frozen=True)
class ResultadoLaneDispatch:
    rota: RotaSemantica
    estado: EstadoLaneDispatch
    detalhe: str

    def __post_init__(self) -> None:
        if self.rota is RotaSemantica.DROP:
            raise ValueError("DROP nao produz resultado de lane")
        if not isinstance(self.detalhe, str) or not self.detalhe.strip():
            raise ValueError("detalhe obrigatorio")
        if len(self.detalhe) > 128:
            raise ValueError("detalhe excede bound")

@dataclass(frozen=True)
class ResultadoFastDispatch:
    solicitadas: tuple[RotaSemantica, ...]
    resultados: tuple[ResultadoLaneDispatch, ...]

    def __post_init__(self) -> None:
        solicitadas = tuple(self.solicitadas)
        resultados = tuple(self.resultados)
        if not solicitadas:
            raise ValueError("dispatch exige ao menos uma rota solicitada")
        if len(set(solicitadas)) != len(solicitadas):
            raise ValueError("rotas solicitadas duplicadas")
        if RotaSemantica.DROP in solicitadas:
            if len(solicitadas) != 1 or resultados:
                raise ValueError("DROP deve ser exclusivo e sem entrega")
        else:
            rotas_resultado = tuple(item.rota for item in resultados)
            if rotas_resultado != solicitadas:
                raise ValueError("resultados devem corresponder as rotas solicitadas")
        object.__setattr__(self, "solicitadas", solicitadas)
        object.__setattr__(self, "resultados", resultados)

    @property
    def entregues(self) -> tuple[RotaSemantica, ...]:
        return tuple(item.rota for item in self.resultados if item.estado is EstadoLaneDispatch.DELIVERED)

    @property
    def deferidas(self) -> tuple[RotaSemantica, ...]:
        return tuple(item.rota for item in self.resultados if item.estado is EstadoLaneDispatch.DEFERRED)

    @property
    def falhas(self) -> tuple[RotaSemantica, ...]:
        return tuple(item.rota for item in self.resultados if item.estado is EstadoLaneDispatch.FAILED)

    def to_dict(self) -> dict[str, object]:
        return {
            "solicitadas": [rota.value for rota in self.solicitadas],
            "resultados": [
                {"rota": item.rota.value, "estado": item.estado.value, "detalhe": item.detalhe}
                for item in self.resultados
            ],
        }
