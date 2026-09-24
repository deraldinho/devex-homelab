"""Atlas Temporal Correlator — Correlação de eventos co-ocorrentes.

Detecta padrões temporais entre eventos para identificar
relações causais ou correlações recorrentes.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TemporalCorrelation:
    """Correlação detectada entre dois tipos de evento."""
    event_a: str
    event_b: str
    co_occurrences: int
    total_a: int
    total_b: int
    confidence: float          # co_occurrences / min(total_a, total_b)
    mean_delay_seconds: float  # média de delay entre A e B
    pattern: str               # "simultaneous", "a_precedes_b", "b_precedes_a"
    first_seen: str
    last_seen: str


@dataclass
class _EventEntry:
    event_type: str
    timestamp_epoch: float
    node: str = ""


class TemporalCorrelator:
    """Correlacionador temporal leve.

    Mantém janela limitada de eventos recentes e detecta
    co-ocorrências dentro de uma janela temporal configurável.
    """

    DEFAULT_WINDOW_SECONDS = 300.0   # 5 minutos
    DEFAULT_MIN_COOCCURRENCES = 3
    DEFAULT_MAX_EVENTS = 500
    DEFAULT_MAX_PATTERNS = 100

    def __init__(
        self,
        *,
        window_seconds: float = 300.0,
        min_cooccurrences: int = 3,
        max_events: int = 500,
        max_patterns: int = 100,
        known_rules: dict[tuple[str, str], str] | None = None,
    ):
        self._window_seconds = window_seconds
        self._min_cooccurrences = min_cooccurrences
        self._max_events = max_events
        self._max_patterns = max_patterns
        self._events: list[_EventEntry] = []
        self._co_occurrence_count: dict[tuple[str, str], int] = defaultdict(int)
        self._total_by_type: dict[str, int] = defaultdict(int)
        self._delay_sums: dict[tuple[str, str], float] = defaultdict(float)
        self._first_seen: dict[tuple[str, str], str] = {}
        self._last_seen: dict[tuple[str, str], str] = {}
        # known_rules: pares de tipos de evento com interpretação fixa
        # ex: {("cpu_high", "swap_high"): "pressao de memoria"}
        self._known_rules = known_rules or {}

    def record_event(
        self,
        event_type: str,
        timestamp: str = "",
        node: str = "",
    ) -> list[TemporalCorrelation]:
        """Registra evento e retorna correlações significativas detectadas."""
        ts = timestamp or _utc_now()
        try:
            epoch = datetime.fromisoformat(ts).timestamp()
        except ValueError:
            epoch = datetime.now(timezone.utc).timestamp()

        entry = _EventEntry(event_type, epoch, node)
        self._events.append(entry)
        self._total_by_type[event_type] += 1

        # Limitar tamanho da janela
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

        # Buscar co-ocorrências na janela temporal
        new_correlations: list[TemporalCorrelation] = []
        for past in self._events[:-1]:
            delay = abs(epoch - past.timestamp_epoch)
            if delay > self._window_seconds:
                continue
            if past.event_type == event_type:
                continue

            pair = tuple(sorted([event_type, past.event_type]))
            pair_key = (pair[0], pair[1])
            self._co_occurrence_count[pair_key] += 1
            self._delay_sums[pair_key] += delay

            if pair_key not in self._first_seen:
                self._first_seen[pair_key] = ts
            self._last_seen[pair_key] = ts

            count = self._co_occurrence_count[pair_key]
            if count >= self._min_cooccurrences:
                total_a = self._total_by_type[pair_key[0]]
                total_b = self._total_by_type[pair_key[1]]
                min_total = min(total_a, total_b) if min(total_a, total_b) > 0 else 1
                confidence = count / min_total
                mean_delay = self._delay_sums[pair_key] / count

                if mean_delay < 5.0:
                    pattern = "simultaneous"
                elif epoch > past.timestamp_epoch:
                    pattern = "a_precedes_b" if pair_key[0] == past.event_type else "b_precedes_a"
                else:
                    pattern = "b_precedes_a" if pair_key[0] == past.event_type else "a_precedes_b"

                corr = TemporalCorrelation(
                    event_a=pair_key[0],
                    event_b=pair_key[1],
                    co_occurrences=count,
                    total_a=total_a,
                    total_b=total_b,
                    confidence=min(1.0, confidence),
                    mean_delay_seconds=mean_delay,
                    pattern=pattern,
                    first_seen=self._first_seen[pair_key],
                    last_seen=ts,
                )
                new_correlations.append(corr)

        return new_correlations

    def get_known_interpretation(self, event_a: str, event_b: str) -> str | None:
        """Retorna interpretação conhecida para um par de eventos, se existir."""
        pair = tuple(sorted([event_a, event_b]))
        return self._known_rules.get((pair[0], pair[1]))

    def get_all_correlations(self) -> list[TemporalCorrelation]:
        """Retorna todas as correlações significativas."""
        correlations: list[TemporalCorrelation] = []
        for pair_key, count in self._co_occurrence_count.items():
            if count < self._min_cooccurrences:
                continue
            total_a = self._total_by_type[pair_key[0]]
            total_b = self._total_by_type[pair_key[1]]
            min_total = min(total_a, total_b) if min(total_a, total_b) > 0 else 1
            mean_delay = self._delay_sums[pair_key] / count if count > 0 else 0.0

            correlations.append(TemporalCorrelation(
                event_a=pair_key[0],
                event_b=pair_key[1],
                co_occurrences=count,
                total_a=total_a,
                total_b=total_b,
                confidence=min(1.0, count / min_total),
                mean_delay_seconds=mean_delay,
                pattern="simultaneous" if mean_delay < 5.0 else "sequential",
                first_seen=self._first_seen.get(pair_key, ""),
                last_seen=self._last_seen.get(pair_key, ""),
            ))
        correlations.sort(key=lambda c: c.confidence, reverse=True)
        return correlations[:self._max_patterns]

    def event_count(self) -> int:
        return len(self._events)
