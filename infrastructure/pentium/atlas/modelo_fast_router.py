from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RotaSemantica(str, Enum):
    DROP = "drop"
    FAST_REACTION = "fast_reaction"
    AFFECT = "affect"
    CACHE_LOOKUP = "cache_lookup"
    SLOW_LLM = "slow_llm"


@dataclass(frozen=True)
class DecisaoFastRouter:
    rotas: tuple[RotaSemantica, ...]
    motivo: str
    score: float

    def __post_init__(self) -> None:
        rotas = tuple(self.rotas)
        if not rotas:
            raise ValueError("decisao exige ao menos uma rota")
        if len(set(rotas)) != len(rotas):
            raise ValueError("rotas duplicadas")
        if RotaSemantica.DROP in rotas and len(rotas) != 1:
            raise ValueError("DROP deve ser exclusivo")

        if not isinstance(self.motivo, str) or not self.motivo.strip():
            raise ValueError("motivo obrigatorio")
        if len(self.motivo) > 128:
            raise ValueError("motivo excede bound")
        score = float(self.score)
        if not 0.0 <= score <= 1.0:
            raise ValueError("score deve estar entre 0 e 1")
        object.__setattr__(self, "rotas", rotas)
        object.__setattr__(self, "score", score)

    def to_dict(self) -> dict[str, object]:
        return {
            "rotas": [rota.value for rota in self.rotas],
            "motivo": self.motivo,
            "score": self.score,
        }
