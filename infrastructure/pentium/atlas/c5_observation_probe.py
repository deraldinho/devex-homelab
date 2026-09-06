from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .observation_runtime import ObservationRuntime
from .stimulus_bus import StimulusBus
from .stimulus_sources import PentiumSelfSource


class C5ObservationProbe:
    def __init__(
        self,
        state_path: Path,
        *,
        max_age_s: float,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        if max_age_s <= 0:
            raise ValueError("max_age_s deve ser > 0")
        self._state_path = Path(state_path).expanduser()
        self._max_age_s = float(max_age_s)
        self._now = now
        self._last_payload: dict[str, object] | None = None
        self._bus = StimulusBus(capacity=8)
        self._source = PentiumSelfSource(self._collect)
        self._runtime = ObservationRuntime(
            sources=[self._source],
            bus=self._bus,
            journal=lambda _stimulus: None,
        )

    def _collect(self) -> dict[str, object]:
        payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("heartbeat state invalido")
        checked_at = payload.get("checked_at")
        if not isinstance(checked_at, str):
            raise ValueError("heartbeat sem checked_at")
        instante = datetime.fromisoformat(checked_at)
        if instante.tzinfo is None or instante.utcoffset() is None:
            raise ValueError("checked_at sem timezone")
        agora = self._now()
        if agora.tzinfo is None or agora.utcoffset() is None:
            raise ValueError("now sem timezone")
        idade = (agora.astimezone(timezone.utc) - instante.astimezone(timezone.utc)).total_seconds()
        if idade < 0 or idade > self._max_age_s:
            raise ValueError("heartbeat stale")
        self._last_payload = payload
        return payload

    def __call__(self) -> bool:
        erros_antes = len(self._runtime.errors())
        try:
            stimulus = self._runtime.run_once(self._source.name)
            if stimulus is not None and stimulus.kind == "source_error":
                return False
            if self._last_payload is None:
                return False
            return len(self._runtime.errors()) == erros_antes
        except Exception:
            return False
        finally:
            while self._bus.poll() is not None:
                pass

    def close(self) -> None:
        self._runtime.close()
