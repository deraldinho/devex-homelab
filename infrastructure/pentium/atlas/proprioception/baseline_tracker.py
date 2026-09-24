"""Atlas Baseline Tracker — Baselines adaptativos por métrica/nó.

Mantém estatísticas rolling (média, desvio padrão, percentis)
por métrica + nó, permitindo detecção de desvios significativos
sem acumular histórico bruto.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class BaselineStats:
    """Estatísticas rolling para uma métrica/nó."""
    count: int = 0
    mean: float = 0.0
    m2: float = 0.0          # Para cálculo incremental de variância (Welford)
    min_value: float = float("inf")
    max_value: float = float("-inf")
    last_value: float = 0.0
    last_updated: str = ""

    @property
    def variance(self) -> float:
        if self.count < 2:
            return 0.0
        return self.m2 / (self.count - 1)

    @property
    def stddev(self) -> float:
        return math.sqrt(self.variance)

    def is_deviation(self, value: float, sigma: float = 2.0) -> bool:
        """Retorna True se o valor está fora de `sigma` desvios padrão."""
        if self.count < 5:
            return False
        sd = self.stddev
        if sd < 1e-10:
            return False
        return abs(value - self.mean) > sigma * sd

    def z_score(self, value: float) -> float:
        """Retorna o z-score do valor em relação ao baseline."""
        if self.count < 5 or self.stddev < 1e-10:
            return 0.0
        return (value - self.mean) / self.stddev


@dataclass(frozen=True)
class BaselineDeviation:
    """Evento de desvio significativo do baseline."""
    metric_key: str
    node: str
    value: float
    baseline_mean: float
    baseline_stddev: float
    z_score: float
    consecutive_deviations: int
    timestamp: str


class BaselineTracker:
    """Motor de baselines adaptativos.

    Usa algoritmo de Welford para estatísticas incrementais eficientes.
    Persiste em JSON para leveza no Pentium.
    """

    DEFAULT_SIGMA = 2.0
    DEFAULT_HYSTERESIS = 3       # N ciclos consecutivos para alertar
    MAX_METRICS = 200            # Limite de métricas rastreadas

    def __init__(self, path: Path, *, sigma: float = 2.0, hysteresis: int = 3):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._sigma = sigma
        self._hysteresis = hysteresis
        self._stats: dict[str, BaselineStats] = {}
        self._consecutive_deviations: dict[str, int] = {}
        self._load()

    @staticmethod
    def metric_key(node: str, metric: str) -> str:
        """Gera chave determinística para métrica/nó."""
        return f"{node}:{metric}"

    def update(self, node: str, metric: str, value: float, timestamp: str = "") -> BaselineDeviation | None:
        """Atualiza baseline com novo valor. Retorna desvio se significativo e sustentado."""
        key = self.metric_key(node, metric)
        ts = timestamp or _utc_now()

        stats = self._stats.get(key)
        if stats is None:
            if len(self._stats) >= self.MAX_METRICS:
                return None
            stats = BaselineStats()
            self._stats[key] = stats

        # Welford online update
        stats.count += 1
        delta = value - stats.mean
        stats.mean += delta / stats.count
        delta2 = value - stats.mean
        stats.m2 += delta * delta2
        stats.min_value = min(stats.min_value, value)
        stats.max_value = max(stats.max_value, value)
        stats.last_value = value
        stats.last_updated = ts

        # Detecção de desvio
        if stats.is_deviation(value, self._sigma):
            self._consecutive_deviations[key] = self._consecutive_deviations.get(key, 0) + 1
            if self._consecutive_deviations[key] >= self._hysteresis:
                return BaselineDeviation(
                    metric_key=key,
                    node=node,
                    value=value,
                    baseline_mean=stats.mean,
                    baseline_stddev=stats.stddev,
                    z_score=stats.z_score(value),
                    consecutive_deviations=self._consecutive_deviations[key],
                    timestamp=ts,
                )
        else:
            self._consecutive_deviations[key] = 0

        return None

    def get_stats(self, node: str, metric: str) -> BaselineStats | None:
        return self._stats.get(self.metric_key(node, metric))

    def get_all_stats(self) -> dict[str, BaselineStats]:
        return dict(self._stats)

    def save(self) -> None:
        """Persiste baselines em JSON."""
        data: dict[str, dict] = {}
        for key, stats in self._stats.items():
            data[key] = {
                "count": stats.count,
                "mean": stats.mean,
                "m2": stats.m2,
                "min_value": stats.min_value if stats.min_value != float("inf") else None,
                "max_value": stats.max_value if stats.max_value != float("-inf") else None,
                "last_value": stats.last_value,
                "last_updated": stats.last_updated,
            }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for key, item in data.items():
                self._stats[key] = BaselineStats(
                    count=int(item["count"]),
                    mean=float(item["mean"]),
                    m2=float(item["m2"]),
                    min_value=float(item["min_value"]) if item.get("min_value") is not None else float("inf"),
                    max_value=float(item["max_value"]) if item.get("max_value") is not None else float("-inf"),
                    last_value=float(item.get("last_value", 0.0)),
                    last_updated=str(item.get("last_updated", "")),
                )
        except (json.JSONDecodeError, TypeError, KeyError):
            pass
