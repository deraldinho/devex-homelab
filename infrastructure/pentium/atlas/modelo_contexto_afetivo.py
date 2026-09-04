from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum


class TipoEntidadeAfetiva(str, Enum):
    CEREBRO = "cerebro"
    MEMBRO = "membro"
    ORGAO_VITAL = "orgao_vital"
    DEPENDENCIA_EXTERNA = "dependencia_externa"
    RECURSO_EXTERNO = "recurso_externo"
    PROJETO = "projeto"
    SERVICO = "servico"


def _texto_obrigatorio(valor: str, nome: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nome} nao pode ser vazio")
    return valor.strip()


def _finito(valor: float, nome: str) -> float:
    numero = float(valor)
    if not math.isfinite(numero):
        raise ValueError(f"{nome} deve ser finito")
    return numero

def _limitar_01(valor: float, nome: str) -> float:
    return max(0.0, min(1.0, _finito(valor, nome)))


def _delta_experiencial(valor: float, nome: str) -> float:
    numero = _finito(valor, nome)
    if not -1.0 <= numero <= 1.0:
        raise ValueError(f"{nome} deve estar entre -1.0 e 1.0")
    return numero


@dataclass(frozen=True)
class EntidadeAfetiva:
    entidade_id: str
    nome: str
    tipo: TipoEntidadeAfetiva
    incorporada: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "entidade_id", _texto_obrigatorio(self.entidade_id, "entidade_id"))
        object.__setattr__(self, "nome", _texto_obrigatorio(self.nome, "nome"))
        if not isinstance(self.tipo, TipoEntidadeAfetiva):
            object.__setattr__(self, "tipo", TipoEntidadeAfetiva(self.tipo))
        if not isinstance(self.incorporada, bool):
            raise ValueError("incorporada deve ser booleana")

    def incorporar(self) -> "EntidadeAfetiva":
        if self.tipo is not TipoEntidadeAfetiva.MEMBRO:
            raise ValueError("somente entidades MEMBRO possuem incorporacao explicita")
        return replace(self, incorporada=True)

@dataclass(frozen=True)
class VinculoAfetivo:
    entidade_id: str
    importancia: float
    proximidade: float
    responsabilidade: float
    dependencia_operacional: float
    familiaridade: float
    confianca_operacional: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "entidade_id", _texto_obrigatorio(self.entidade_id, "entidade_id"))
        for nome in (
            "importancia", "proximidade", "responsabilidade",
            "dependencia_operacional", "familiaridade", "confianca_operacional",
        ):
            object.__setattr__(self, nome, _limitar_01(getattr(self, nome), nome))

    def evoluir_experiencia(
        self,
        delta_familiaridade: float,
        delta_confianca_operacional: float,
    ) -> "VinculoAfetivo":
        df = _delta_experiencial(delta_familiaridade, "delta_familiaridade")
        dc = _delta_experiencial(delta_confianca_operacional, "delta_confianca_operacional")
        return replace(
            self,
            familiaridade=_limitar_01(self.familiaridade + df, "familiaridade"),
            confianca_operacional=_limitar_01(self.confianca_operacional + dc, "confianca_operacional"),
        )
