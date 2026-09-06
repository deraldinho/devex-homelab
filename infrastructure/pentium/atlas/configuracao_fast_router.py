from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PoliticaFastRouter:
    drop_score_max: float
    cache_novelty_max: float
    fast_reaction_score_min: float
    slow_llm_score_min: float
    slow_llm_score_max: float
    slow_llm_novelty_min: float

    def __post_init__(self) -> None:
        campos = (
            "drop_score_max",
            "cache_novelty_max",
            "fast_reaction_score_min",
            "slow_llm_score_min",
            "slow_llm_score_max",
            "slow_llm_novelty_min",
        )
        for campo in campos:
            valor = float(getattr(self, campo))
            if not 0.0 <= valor <= 1.0:
                raise ValueError(f"{campo} deve estar entre 0 e 1")
            object.__setattr__(self, campo, valor)

        if not (
            self.drop_score_max < self.slow_llm_score_min
            <= self.slow_llm_score_max
            < self.fast_reaction_score_min
        ):
            raise ValueError("thresholds de score sobrepostos")


def carregar_politica_fast_router(path: Path) -> PoliticaFastRouter:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("config fast router schema_version deve ser 1")
    try:
        return PoliticaFastRouter(
            drop_score_max=payload["drop_score_max"],
            cache_novelty_max=payload["cache_novelty_max"],
            fast_reaction_score_min=payload["fast_reaction_score_min"],
            slow_llm_score_min=payload["slow_llm_score_min"],
            slow_llm_score_max=payload["slow_llm_score_max"],
            slow_llm_novelty_min=payload["slow_llm_novelty_min"],
        )
    except KeyError as exc:
        raise ValueError(f"config fast router sem {exc.args[0]}") from exc
