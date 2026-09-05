from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class EstadoObservacao(str, Enum):
    OBSERVADO = "observado"
    PARCIALMENTE_OBSERVADO = "parcialmente_observado"
    INACESSIVEL = "inacessivel"
    DESCONHECIDO = "desconhecido"


class ResultadoEvidencia(str, Enum):
    DISPONIVEL = "disponivel"
    INDISPONIVEL = "indisponivel"
    FONTE_INDISPONIVEL = "fonte_indisponivel"
    INCONCLUSIVA = "inconclusiva"


def _utc(valor: str, nome: str) -> str:
    instante = datetime.fromisoformat(valor)
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError(f"{nome} deve possuir timezone")
    return instante.astimezone(timezone.utc).isoformat()


def _texto(valor: str, nome: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nome} nao pode ser vazio")
    return valor.strip()

@dataclass(frozen=True)
class EvidenciaPercepcao:
    evidencia_id: str
    entidade_id: str
    fonte: str
    resultado: ResultadoEvidencia
    confianca: float
    observado_em: str
    conclusiva: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidencia_id", _texto(self.evidencia_id, "evidencia_id"))
        object.__setattr__(self, "entidade_id", _texto(self.entidade_id, "entidade_id"))
        object.__setattr__(self, "fonte", _texto(self.fonte, "fonte"))
        if not isinstance(self.resultado, ResultadoEvidencia):
            object.__setattr__(self, "resultado", ResultadoEvidencia(self.resultado))
        object.__setattr__(self, "confianca", max(0.0, min(1.0, float(self.confianca))))
        object.__setattr__(self, "observado_em", _utc(self.observado_em, "observado_em"))
        if not isinstance(self.conclusiva, bool):
            raise ValueError("conclusiva deve ser booleana")


@dataclass(frozen=True)
class EstadoPercepcao:
    entidade_id: str
    estado: EstadoObservacao
    confianca: float
    ultima_observacao_valida: str | None
    fontes_disponiveis: tuple[str, ...]
    fontes_indisponiveis: tuple[str, ...]
    conflito_evidencias: bool
    atualizado_em: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "entidade_id", _texto(self.entidade_id, "entidade_id"))
        if not isinstance(self.estado, EstadoObservacao):
            object.__setattr__(self, "estado", EstadoObservacao(self.estado))
        object.__setattr__(self, "confianca", max(0.0, min(1.0, float(self.confianca))))
        if self.ultima_observacao_valida is not None:
            object.__setattr__(
                self,
                "ultima_observacao_valida",
                _utc(self.ultima_observacao_valida, "ultima_observacao_valida"),
            )
        object.__setattr__(
            self,
            "fontes_disponiveis",
            tuple(sorted(set(self.fontes_disponiveis))),
        )
        object.__setattr__(
            self,
            "fontes_indisponiveis",
            tuple(sorted(set(self.fontes_indisponiveis))),
        )
        object.__setattr__(self, "atualizado_em", _utc(self.atualizado_em, "atualizado_em"))
