from __future__ import annotations


class EpisodicMetrics:
    def __init__(self):
        self._values: dict[str, float] = {}

    def increment(self, name: str, value: float = 1.0) -> None:
        self._values[name] = self._values.get(name, 0.0) + float(value)

    def set(self, name: str, value: float) -> None:
        self._values[name] = float(value)

    def get(self, name: str) -> float:
        return self._values.get(name, 0.0)

    def snapshot(self) -> dict[str, float]:
        return dict(sorted(self._values.items()))
