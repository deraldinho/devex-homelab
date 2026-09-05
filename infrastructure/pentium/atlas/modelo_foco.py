from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone


def _texto(valor: str, nome: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nome} nao pode ser vazio")
    return valor.strip()


def _limitar_01(valor: float, nome: str) -> float:
    numero = float(valor)
    if not math.isfinite(numero):
        raise ValueError(f"{nome} deve ser finito")
    return max(0.0, min(1.0, numero))


def _utc(valor: str) -> str:
    instante = datetime.fromisoformat(valor)
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("atualizado_em deve possuir timezone")
    return instante.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class AssuntoFoco:
    assunto_id: str
    entidade_id: str
    gravidade: float
    impacto_afetivo: float
    importancia: float
    novidade: float
    urgencia: float
    recencia: float
    critico: bool = False
    recuperado: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "assunto_id", _texto(self.assunto_id, "assunto_id"))
        object.__setattr__(self, "entidade_id", _texto(self.entidade_id, "entidade_id"))
        for nome in (
            "gravidade", "impacto_afetivo", "importancia",
            "novidade", "urgencia", "recencia",
        ):
            object.__setattr__(self, nome, _limitar_01(getattr(self, nome), nome))
        if not isinstance(self.critico, bool) or not isinstance(self.recuperado, bool):
            raise ValueError("critico e recuperado devem ser booleanos")


@dataclass(frozen=True)
class PoliticaFoco:
    capacidade_secundarios: int
    margem_histerese: float
    fator_recuperacao: float

    def __post_init__(self) -> None:
        if not isinstance(self.capacidade_secundarios, int) or self.capacidade_secundarios <= 0:
            raise ValueError("capacidade_secundarios deve ser inteiro > 0")
        object.__setattr__(self, "margem_histerese", _limitar_01(self.margem_histerese, "margem_histerese"))
        object.__setattr__(self, "fator_recuperacao", _limitar_01(self.fator_recuperacao, "fator_recuperacao"))


@dataclass(frozen=True)
class FocoAtencao:
    principal: AssuntoFoco | None
    secundarios: tuple[AssuntoFoco, ...]
    atualizado_em: str
    capacidade_secundarios: int

    def __post_init__(self) -> None:
        if not isinstance(self.capacidade_secundarios, int) or self.capacidade_secundarios <= 0:
            raise ValueError("capacidade_secundarios deve ser inteiro > 0")
        object.__setattr__(self, "atualizado_em", _utc(self.atualizado_em))
        vistos: set[str] = set()
        itens: list[AssuntoFoco] = []
        principal_id = self.principal.assunto_id if self.principal else None
        for item in self.secundarios:
            if item.assunto_id == principal_id or item.assunto_id in vistos:
                continue
            vistos.add(item.assunto_id)
            itens.append(item)
        object.__setattr__(self, "secundarios", tuple(itens[: self.capacidade_secundarios]))
