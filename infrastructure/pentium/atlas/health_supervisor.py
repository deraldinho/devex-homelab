from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .health_supervisor_model import ComponentHealth, ComponentHealthState


_SEVERITY = {
    ComponentHealthState.HEALTHY: 0,
    ComponentHealthState.PAUSED_INTENTIONALLY: 0,
    ComponentHealthState.UNKNOWN: 1,
    ComponentHealthState.DEGRADED: 2,
    ComponentHealthState.RECOVERING: 3,
    ComponentHealthState.STALE: 4,
    ComponentHealthState.DISCONNECTED: 5,
    ComponentHealthState.FAILED: 6,
}


@dataclass(frozen=True)
class EvaluatedComponentHealth:
    component_id: str
    host: str
    expected_state: str
    state: ComponentHealthState
    observed_at: str
    reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    required: bool = True

    def to_dict(self) -> dict:
        return {
            "component_id": self.component_id,
            "host": self.host,
            "expected_state": self.expected_state,
            "state": self.state.value,
            "observed_at": self.observed_at,
            "reasons": list(self.reasons),
            "evidence_refs": list(self.evidence_refs),
            "required": self.required,
        }


@dataclass(frozen=True)
class SupervisorSnapshot:
    generated_at: str
    state: ComponentHealthState
    components: tuple[EvaluatedComponentHealth, ...]

    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "generated_at": self.generated_at,
            "state": self.state.value,
            "components": [item.to_dict() for item in self.components],
        }


class AtlasHealthSupervisor:
    def _component_state(self, component: ComponentHealth) -> tuple[ComponentHealthState, tuple[str, ...]]:
        if component.expected_state.strip().lower() == "paused":
            return ComponentHealthState.PAUSED_INTENTIONALLY, ("expected_paused",)

        dims = (
            ("process", component.process_state),
            ("functional", component.functional_state),
            ("freshness", component.freshness),
            ("dependency", component.dependency_state),
        )
        states = {name: dim.state for name, dim in dims}

        if states["process"] is ComponentHealthState.FAILED or states["functional"] is ComponentHealthState.FAILED:
            state = ComponentHealthState.FAILED
        elif states["process"] is ComponentHealthState.DISCONNECTED or states["functional"] is ComponentHealthState.DISCONNECTED:
            state = ComponentHealthState.DISCONNECTED
        elif states["freshness"] is ComponentHealthState.STALE:
            state = ComponentHealthState.STALE
        elif ComponentHealthState.RECOVERING in states.values():
            state = ComponentHealthState.RECOVERING
        elif states["dependency"] in {
            ComponentHealthState.FAILED,
            ComponentHealthState.DISCONNECTED,
            ComponentHealthState.STALE,
        }:
            state = ComponentHealthState.DEGRADED
        elif ComponentHealthState.DEGRADED in states.values():
            state = ComponentHealthState.DEGRADED
        elif ComponentHealthState.UNKNOWN in states.values():
            state = ComponentHealthState.UNKNOWN
        else:
            state = ComponentHealthState.HEALTHY

        reasons = tuple(
            f"{name}:{dim.reason or dim.state.value}"
            for name, dim in dims
            if dim.state is not ComponentHealthState.HEALTHY
        )
        return state, reasons

    def evaluate(self, components: tuple[ComponentHealth, ...], now: str) -> SupervisorSnapshot:
        evaluated = []
        for component in components:
            state, reasons = self._component_state(component)
            evaluated.append(
                EvaluatedComponentHealth(
                    component_id=component.component_id,
                    host=component.host,
                    expected_state=component.expected_state,
                    state=state,
                    observed_at=component.observed_at,
                    reasons=reasons,
                    evidence_refs=component.evidence_refs,
                    required=component.required,
                )
            )

        required = [
            item
            for item in evaluated
            if item.required and item.state is not ComponentHealthState.PAUSED_INTENTIONALLY
        ]
        state = (
            max(required, key=lambda item: _SEVERITY[item.state]).state
            if required
            else ComponentHealthState.HEALTHY
        )
        return SupervisorSnapshot(str(now), state, tuple(evaluated))


class HealthSnapshotPublisher:
    def __init__(self, snapshot_path: Path, events_path: Path, *, max_events: int = 256):
        self.snapshot_path = Path(snapshot_path)
        self.events_path = Path(events_path)
        self.max_events = max(1, int(max_events))

    def _atomic_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)

    def _existing_events(self) -> list[dict]:
        if not self.events_path.is_file():
            return []
        result = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                result.append(item)
        return result

    def _write_events(self, events: list[dict]) -> None:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.events_path.with_name(self.events_path.name + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8", newline="\n") as handle:
                for item in events[-self.max_events:]:
                    handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.events_path)
        finally:
            tmp.unlink(missing_ok=True)

    def publish(self, snapshot: SupervisorSnapshot) -> dict:
        payload = snapshot.to_dict()
        previous_state = None
        if self.snapshot_path.is_file():
            try:
                previous_state = json.loads(
                    self.snapshot_path.read_text(encoding="utf-8")
                ).get("state")
            except (OSError, json.JSONDecodeError, AttributeError):
                previous_state = None

        self._atomic_json(self.snapshot_path, payload)

        current_state = snapshot.state.value
        if previous_state != current_state:
            transition = "changed"
            if (
                previous_state in {
                    ComponentHealthState.DEGRADED.value,
                    ComponentHealthState.STALE.value,
                    ComponentHealthState.DISCONNECTED.value,
                    ComponentHealthState.FAILED.value,
                    ComponentHealthState.RECOVERING.value,
                }
                and snapshot.state is ComponentHealthState.HEALTHY
            ):
                transition = "recovered"
            events = self._existing_events()
            events.append(
                {
                    "timestamp": snapshot.generated_at,
                    "state": current_state,
                    "previous_state": previous_state,
                    "transition": transition,
                }
            )
            self._write_events(events)
        return payload
