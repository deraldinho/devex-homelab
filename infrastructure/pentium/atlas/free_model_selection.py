"""Fail-closed, zero-price model choice for trusted runtime metadata.

Does not initiate inference or confer authorization to invoke providers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ModelOffer:
    provider: str
    model: str
    input_price_per_million: float | None
    output_price_per_million: float | None
    zero_cost_verified: bool
    tasks: frozenset[str]
    quality_score: float = 0.0
    latency_ms: float = 10000.0
    quota_available: bool = True
    cooldown: bool = False


def select_free_models(
    offers: Iterable[ModelOffer], *, task: str, authorized: frozenset[tuple[str, str]]
) -> tuple[ModelOffer, ...]:
    """Never infer entitlement from naming or model presence in a catalog."""
    if not task or not isinstance(task, str):
        raise ValueError("task required")
    chosen: list[ModelOffer] = []
    seen: set[tuple[str, str]] = set()
    for model in offers:
        identity = (model.provider, model.model)
        if identity in seen:
            continue
        seen.add(identity)
        if identity not in authorized or task not in model.tasks:
            continue
        if not model.zero_cost_verified or not model.quota_available or model.cooldown:
            continue
        if model.input_price_per_million != 0 or model.output_price_per_million != 0:
            continue
        chosen.append(model)
    return tuple(sorted(chosen, key=lambda m: (-m.quality_score, m.latency_ms, m.provider, m.model)))
