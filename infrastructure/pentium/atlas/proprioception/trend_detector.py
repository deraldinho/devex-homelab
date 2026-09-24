"""Atlas Trend Detector — Detecção de tendências lineares por métrica.

Calcula regressão linear sobre janela curta de pontos por métrica
para detectar tendências de degradação ou melhoria sustentadas.
Projeta estimativa de esgotamento para métricas de capacidade.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TrendEvent:
    """Evento de tendência detectada."""
    metric_key: str
    node: str
    metric: str
    direction: str           # "rising" ou "falling"
    slope: float             # unidade/hora
    confidence: float        # R² da regressão
    current_value: float
    projected_value: float   # valor projetado em projection_hours
    projection_hours: float
    exhaustion_hours: float | None  # horas até esgotar (se aplicável)
    window_size: int
    timestamp: str


@dataclass
class _MetricWindow:
    """Janela deslizante de valores para uma métrica."""
    timestamps: list[float] = field(default_factory=list)  # epoch seconds
    values: list[float] = field(default_factory=list)
    max_size: int = 20

    def add(self, timestamp_epoch: float, value: float) -> None:
        self.timestamps.append(timestamp_epoch)
        self.values.append(value)
        if len(self.timestamps) > self.max_size:
            self.timestamps.pop(0)
            self.values.pop(0)


def _linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Retorna (slope, intercept, r_squared) para regressão linear simples."""
    n = len(xs)
    if n < 3:
        return 0.0, 0.0, 0.0

    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    sum_x2 = sum(x * x for x in xs)
    sum_y2 = sum(y * y for y in ys)

    denom = n * sum_x2 - sum_x * sum_x
    if abs(denom) < 1e-10:
        return 0.0, sum_y / n, 0.0

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n

    # R² (coefficient of determination)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - sum_y / n) ** 2 for y in ys)
    r_squared = 1.0 - ss_res / ss_tot if abs(ss_tot) > 1e-10 else 0.0

    return slope, intercept, max(0.0, r_squared)


class TrendDetector:
    """Detector de tendências lineares por métrica/nó.

    Usa janela deslizante de valores e regressão linear simples.
    Emite TrendEvents quando a tendência é sustentada e confiável.
    """

    DEFAULT_MIN_POINTS = 5
    DEFAULT_MIN_CONFIDENCE = 0.6
    DEFAULT_MIN_SLOPE_MAGNITUDE = 0.001
    DEFAULT_PROJECTION_HOURS = 24.0
    DEFAULT_WINDOW_SIZE = 20

    def __init__(
        self,
        *,
        min_points: int = 5,
        min_confidence: float = 0.6,
        min_slope_magnitude: float = 0.001,
        projection_hours: float = 24.0,
        window_size: int = 20,
        capacity_metrics: dict[str, tuple[float, float]] | None = None,
    ):
        self._min_points = min_points
        self._min_confidence = min_confidence
        self._min_slope_magnitude = min_slope_magnitude
        self._projection_hours = projection_hours
        self._window_size = window_size
        # capacity_metrics: metric_suffix -> (lower_bound, upper_bound)
        # ex: {"disk_percent": (0.0, 100.0), "memory_percent": (0.0, 100.0)}
        self._capacity_metrics = capacity_metrics or {}
        self._windows: dict[str, _MetricWindow] = {}

    @staticmethod
    def metric_key(node: str, metric: str) -> str:
        return f"{node}:{metric}"

    def update(
        self,
        node: str,
        metric: str,
        value: float,
        timestamp: str = "",
    ) -> TrendEvent | None:
        """Atualiza janela e retorna TrendEvent se tendência detectada."""
        key = self.metric_key(node, metric)
        ts = timestamp or _utc_now()
        try:
            epoch = datetime.fromisoformat(ts).timestamp()
        except ValueError:
            epoch = datetime.now(timezone.utc).timestamp()

        window = self._windows.get(key)
        if window is None:
            window = _MetricWindow(max_size=self._window_size)
            self._windows[key] = window

        window.add(epoch, value)

        if len(window.values) < self._min_points:
            return None

        # Normalizar timestamps para horas relativas
        t0 = window.timestamps[0]
        xs = [(t - t0) / 3600.0 for t in window.timestamps]
        ys = list(window.values)

        slope, intercept, r_squared = _linear_regression(xs, ys)

        if r_squared < self._min_confidence:
            return None
        if abs(slope) < self._min_slope_magnitude:
            return None

        direction = "rising" if slope > 0 else "falling"

        # Projeção
        current_hours = xs[-1]
        projected_value = slope * (current_hours + self._projection_hours) + intercept

        # Estimativa de esgotamento para métricas de capacidade
        exhaustion_hours = self._estimate_exhaustion(
            metric, slope, intercept, current_hours, value
        )

        return TrendEvent(
            metric_key=key,
            node=node,
            metric=metric,
            direction=direction,
            slope=slope,
            confidence=r_squared,
            current_value=value,
            projected_value=projected_value,
            projection_hours=self._projection_hours,
            exhaustion_hours=exhaustion_hours,
            window_size=len(window.values),
            timestamp=ts,
        )

    def _estimate_exhaustion(
        self,
        metric: str,
        slope: float,
        intercept: float,
        current_hours: float,
        current_value: float,
    ) -> float | None:
        """Estima horas até esgotar capacidade (se aplicável)."""
        for suffix, (lower, upper) in self._capacity_metrics.items():
            if metric.endswith(suffix):
                if slope > 0 and current_value < upper:
                    hours = (upper - current_value) / slope
                    return max(0.0, hours) if hours > 0 else None
                elif slope < 0 and current_value > lower:
                    hours = (lower - current_value) / slope
                    return max(0.0, hours) if hours > 0 else None
        return None

    def get_window(self, node: str, metric: str) -> tuple[float, ...]:
        """Retorna valores atuais na janela (para debug/observability)."""
        key = self.metric_key(node, metric)
        window = self._windows.get(key)
        return tuple(window.values) if window else ()
