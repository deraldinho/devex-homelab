"""Cost-first model selection for Atlas; unpriced models are never eligible.
A zero price is necessary, not sufficient: caller must verify current entitlement.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class ModelProfile:
    model: str
    input_per_million: float | None
    output_per_million: float | None
    free_entitlement_verified: bool
    capabilities: frozenset[str]
    quality: float = 0.0
    latency_ms: float = 10000.0
    quota_remaining: bool = True
    cooldown: bool = False

def rank_models(models, *, task: str, input_tokens: int = 1000,
                output_tokens: int = 500):
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("negative token estimate")
    eligible=[]
    for m in models:
        if (not m.free_entitlement_verified or
            m.input_per_million is None or m.output_per_million is None or
            m.input_per_million != 0 or m.output_per_million != 0 or
            not m.quota_remaining or m.cooldown or task not in m.capabilities):
            continue
        estimated=(input_tokens*m.input_per_million+
                   output_tokens*m.output_per_million)/1_000_000
        # Among verified zero-cost models, prefer measured quality, then latency.
        eligible.append((estimated,-m.quality,m.latency_ms,m.model,m))
    return [t[-1] for t in sorted(eligible)]
