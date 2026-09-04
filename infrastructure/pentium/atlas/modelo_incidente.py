from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EstadoRecuperacaoIncidente(str, Enum):
    ABERTO = "aberto"
    RECUPERADO = "recuperado"


@dataclass(frozen=True)
class IncidenteTecnico:
    incidente_id: str
    entidade_principal: str
    tipo: str
    gravidade: str
    inicio_em: str
    causa_provavel: str
    confianca_causal: float
    entidades_afetadas: tuple[str, ...]
    total_entidades_afetadas: int
    eventos_correlacionados: tuple[str, ...] = ()
    estado_recuperacao: EstadoRecuperacaoIncidente = EstadoRecuperacaoIncidente.ABERTO
    recuperado_em: str | None = None

    def __post_init__(self) -> None:
        if not self.incidente_id or not self.entidade_principal:
            raise ValueError("incidente_id e entidade_principal sao obrigatorios")
        object.__setattr__(self, "confianca_causal", max(0.0, min(1.0, float(self.confianca_causal))))
        object.__setattr__(self, "entidades_afetadas", tuple(sorted(set(self.entidades_afetadas))))
        object.__setattr__(self, "eventos_correlacionados", tuple(sorted(set(self.eventos_correlacionados))))
        if self.total_entidades_afetadas < len(self.entidades_afetadas):
            raise ValueError("total_entidades_afetadas nao pode ser menor que lista materializada")
