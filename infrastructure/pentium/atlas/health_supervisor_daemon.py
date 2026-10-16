from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import time

try:
    from agent.cli import load_config as load_agent_config, _managed_host_from_config
    from agent.managed_inventory import ManagedInventory
    from agent.managed_read import ManagedReadService
    from agent.ssh_transport import SshTransport
except ImportError:
    from infrastructure.pentium.agent.cli import load_config as load_agent_config, _managed_host_from_config
    from infrastructure.pentium.agent.managed_inventory import ManagedInventory
    from infrastructure.pentium.agent.managed_read import ManagedReadService
    from infrastructure.pentium.agent.ssh_transport import SshTransport

from .health_probes import (
    CognitiveSnapshotProbe,
    DashboardHttpProbe,
    DiscordGatewayProbe,
    JsonTimestampStatusProbe,
    ProbeResult,
    SystemdUserProbe,
)
from .health_supervisor import AtlasHealthSupervisor, HealthSnapshotPublisher, SupervisorSnapshot
from .health_supervisor_model import ComponentHealth, ComponentHealthState, HealthDimension
from .host_adapters import ManagedHostAdapter


ROOT = Path(__file__).resolve().parent
DEFAULT_STATE_DIR = Path.home() / "pentium-agent" / "atlas" / "runtime"
DEFAULT_AGENT_CONFIG = Path.home() / "pentium-agent" / "agent" / "config.json"


@dataclass(frozen=True)
class ServiceProbeBundle:
    component_id: str
    host: str
    expected_state: str
    required: bool
    process_probe: object
    functional_probe: object
    freshness_probe: object | None = None
    dependency_probe: object | None = None


class _StaticProbe:
    def __init__(self, state: ComponentHealthState, reason: str):
        self.state = state
        self.reason = reason

    def probe(self) -> ProbeResult:
        now = datetime.now(timezone.utc).isoformat()
        return ProbeResult(
            self.state is ComponentHealthState.HEALTHY,
            self.state,
            now,
            self.reason,
            (),
            {},
        )


class _ManagedAdapterProbe:
    def __init__(self, adapter: ManagedHostAdapter, operation: str):
        self.adapter = adapter
        self.operation = str(operation)

    def probe(self) -> ProbeResult:
        observation = self.adapter.observe(self.operation)
        return ProbeResult(
            observation.ok,
            observation.state,
            observation.observed_at,
            observation.reason,
            observation.evidence_refs,
            {"host": observation.host, "target": observation.target},
        )


def load_health_supervisor_config(path: Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("health supervisor schema_version must be 1")
    features = payload.get("features")
    if not isinstance(features, dict):
        raise ValueError("features must be an object")
    interval = float(payload.get("poll_interval_s", 0))
    if interval <= 0:
        raise ValueError("poll_interval_s must be > 0")
    if not isinstance(payload.get("components"), dict):
        raise ValueError("components must be an object")
    if not isinstance(payload.get("managed_hosts"), dict):
        raise ValueError("managed_hosts must be an object")
    result = dict(payload)
    result["poll_interval_s"] = interval
    return result


class HealthSupervisorOwner:
    def __init__(
        self,
        supervisor: AtlasHealthSupervisor,
        publisher: HealthSnapshotPublisher,
        bundles: tuple[ServiceProbeBundle, ...],
        *,
        poll_interval_s: float,
        now=lambda: datetime.now(timezone.utc),
        sleeper=time.sleep,
        failure_memory=None,
    ):
        self.supervisor = supervisor
        self.publisher = publisher
        self.bundles = tuple(bundles)
        self.poll_interval_s = float(poll_interval_s)
        if self.poll_interval_s <= 0:
            raise ValueError("poll_interval_s must be > 0")
        self.now = now
        self.sleeper = sleeper
        # Opt-in observer only. No model/tool dispatch or automatic learning.
        self.failure_memory = failure_memory
        self.last_failure_memory_error: str | None = None

    def close(self) -> None:
        if self.failure_memory is not None:
            self.failure_memory.close()

    def _instant(self) -> datetime:
        value = self.now()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("now must return timezone-aware datetime")
        return value.astimezone(timezone.utc)

    def _safe_probe(self, probe, cache: dict[int, ProbeResult]) -> ProbeResult:
        key = id(probe)
        if key in cache:
            return cache[key]
        try:
            result = probe.probe()
        except Exception as exc:
            result = ProbeResult(
                False,
                ComponentHealthState.DEGRADED,
                self._instant().isoformat(),
                f"probe_error:{type(exc).__name__}",
                (),
                {},
            )
        cache[key] = result
        return result

    @staticmethod
    def _dimension(result: ProbeResult) -> HealthDimension:
        return HealthDimension(result.state, result.reason)

    def run_once(self) -> SupervisorSnapshot:
        cache: dict[int, ProbeResult] = {}
        components = []
        now = self._instant()
        for bundle in self.bundles:
            process = self._safe_probe(bundle.process_probe, cache)
            functional = self._safe_probe(bundle.functional_probe, cache)
            freshness = (
                self._safe_probe(bundle.freshness_probe, cache)
                if bundle.freshness_probe is not None
                else functional
            )
            dependency = (
                self._safe_probe(bundle.dependency_probe, cache)
                if bundle.dependency_probe is not None
                else ProbeResult(
                    True,
                    ComponentHealthState.HEALTHY,
                    now.isoformat(),
                    "dependency_not_required",
                    (),
                    {},
                )
            )
            evidence = tuple(dict.fromkeys(
                (*process.evidence_refs, *functional.evidence_refs, *freshness.evidence_refs, *dependency.evidence_refs)
            ))
            components.append(
                ComponentHealth(
                    component_id=bundle.component_id,
                    host=bundle.host,
                    expected_state=bundle.expected_state,
                    process_state=self._dimension(process),
                    functional_state=self._dimension(functional),
                    freshness=self._dimension(freshness),
                    dependency_state=self._dimension(dependency),
                    observed_at=now.isoformat(),
                    evidence_refs=evidence,
                    required=bundle.required,
                )
            )

        snapshot = self.supervisor.evaluate(tuple(components), now.isoformat())
        self.publisher.publish(snapshot)
        if self.failure_memory is not None:
            try:
                self.failure_memory.observe_snapshot(snapshot)
                self.last_failure_memory_error = None
            except Exception as exc:
                # Isolate the advisory store; preserve the core health report.
                # Do not emit incident descriptions/credentials to process logs.
                self.last_failure_memory_error = type(exc).__name__
        return snapshot


def _functional_probe(spec: dict, state_dir: Path):
    expected = str(spec.get("expected_state") or "running").lower()
    if expected == "paused":
        return _StaticProbe(ComponentHealthState.HEALTHY, "expected_paused")
    probe = dict(spec.get("probe") or {})
    kind = str(probe.get("type") or "")
    max_age_s = float(probe.get("max_age_s", 180))
    if kind == "observation_health":
        return JsonTimestampStatusProbe(
            state_dir / str(probe.get("path") or "observation-affective-health.json"),
            timestamp_field="last_cycle_at",
            max_age_s=max_age_s,
            status_field="status",
            healthy_values=("healthy",),
        )
    if kind == "cognitive_snapshot":
        return CognitiveSnapshotProbe(
            state_dir / str(probe.get("path") or "cognitive-runtime.json"),
            max_age_s=max_age_s,
        )
    if kind == "discord_gateway":
        return DiscordGatewayProbe(
            state_dir / str(probe.get("path") or "discord-gateway-health.json"),
            max_age_s=max_age_s,
        )
    if kind == "dashboard_http":
        return DashboardHttpProbe(str(probe["url"]))
    raise ValueError(f"unknown functional probe type: {kind}")


def build_owner(
    *,
    config_root: Path = ROOT,
    state_dir: Path = DEFAULT_STATE_DIR,
    agent_config_path: Path = DEFAULT_AGENT_CONFIG,
) -> HealthSupervisorOwner:
    config_root = Path(config_root)
    state_dir = Path(state_dir)
    config = load_health_supervisor_config(config_root / "config_health_supervisor.json")
    bundles: list[ServiceProbeBundle] = []

    for unit, spec_value in config["components"].items():
        spec = dict(spec_value)
        expected = str(spec.get("expected_state") or "running")
        process = SystemdUserProbe(unit, expected_state=expected)
        functional = _functional_probe(spec, state_dir)
        bundles.append(
            ServiceProbeBundle(
                component_id=unit,
                host=str(spec.get("host") or "pentium"),
                expected_state=expected,
                required=bool(spec.get("required", True)),
                process_probe=process,
                functional_probe=functional,
            )
        )

    enabled_remote = {
        host_id: dict(spec)
        for host_id, spec in config["managed_hosts"].items()
        if bool(spec.get("enabled", False))
    }
    if enabled_remote:
        agent_payload = load_agent_config(Path(agent_config_path))
        inventory = ManagedInventory([
            _managed_host_from_config(item)
            for item in agent_payload["managed_hosts"]
        ])
        read_service = ManagedReadService(inventory, SshTransport())
        for host_id, spec in enabled_remote.items():
            adapter = ManagedHostAdapter(host_id, inventory, read_service)
            probe = _ManagedAdapterProbe(adapter, str(spec.get("operation") or "uptime"))
            bundles.append(
                ServiceProbeBundle(
                    component_id=f"managed.{host_id}",
                    host=host_id,
                    expected_state="running",
                    required=bool(spec.get("required", False)),
                    process_probe=probe,
                    functional_probe=probe,
                )
            )

    publisher = HealthSnapshotPublisher(
        state_dir / "health-supervisor.json",
        state_dir / "health-events.jsonl",
    )
    # Explicitly opt-in to a shared, SQLite WAL, read-only advisory observer.
    # Without the trusted service environment variable, the existing health
    # supervision remains unchanged and creates no extra database.
    failure_memory = None
    if os.environ.get("ATLAS_SENTRY_HEALTH_SHADOW") == "1":
        from .failure_memory import FailureMemory
        failure_memory = FailureMemory(state_dir / "failure-memory.sqlite3")
    return HealthSupervisorOwner(
        AtlasHealthSupervisor(),
        publisher,
        tuple(bundles),
        poll_interval_s=config["poll_interval_s"],
        failure_memory=failure_memory,
    )


def main() -> int:
    config = load_health_supervisor_config(ROOT / "config_health_supervisor.json")
    if not bool(config["features"].get("health_supervisor_v1", False)):
        print("ATLAS_HEALTH_SUPERVISOR_DISABLED", flush=True)
        return 0

    owner = build_owner()
    stop = False

    def request_stop(*_args):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    print("ATLAS_HEALTH_SUPERVISOR_READY", flush=True)
    try:
        while not stop:
            try:
                owner.run_once()
            except Exception as exc:
                print(f"ATLAS_HEALTH_SUPERVISOR_DEGRADED type={type(exc).__name__}", flush=True)
            owner.sleeper(owner.poll_interval_s)
    finally:
        owner.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
