from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import threading
import uuid

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

from .affective_composition import AffectiveComposition, build_affective_composition
from .affective_interaction_ipc import InteractionDatagramListener
from .dual_zone_runtime import build_dual_zone_runtime
from .observation_runtime import load_observation_config
from .presence_persistence import PresenceRepository
from .stimulus_bus import StimulusBus
from .stimulus_journal import append_stimulus
from .stimulus_sources import WifiPresenceSource

ROOT = Path(__file__).resolve().parent
DEFAULT_STATE_DIR = Path.home() / "pentium-agent" / "atlas" / "runtime"
DEFAULT_AGENT_CONFIG = Path.home() / "pentium-agent" / "agent" / "config.json"

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


@dataclass
class ObservationDaemonContext:
    runtime: object
    bus: StimulusBus
    composition: AffectiveComposition
    interaction_listener: object
    health_path: Path
    expected_sha: str | None
    last_cycle_at: str | None = None

    def close(self) -> None:
        try:
            self.interaction_listener.close()
        finally:
            self.runtime.close()

def _managed_service(agent_config_path: Path):
    payload = load_agent_config(agent_config_path)
    hosts = [_managed_host_from_config(item) for item in payload["managed_hosts"]]
    return ManagedReadService(ManagedInventory(hosts), SshTransport()), payload


def build_observation_context(
    *,
    config_root: Path = ROOT,
    agent_config_path: Path = DEFAULT_AGENT_CONFIG,
    state_dir: Path = DEFAULT_STATE_DIR,
    wifi_interface: str,
    managed_read_service=None,
    scanner=None,
    interaction_listener=None,
    expected_sha: str | None = None,
) -> ObservationDaemonContext:
    config_root = Path(config_root)
    state_dir = Path(state_dir)
    agent_payload = load_agent_config(Path(agent_config_path))
    service = managed_read_service
    if service is None:
        service, agent_payload = _managed_service(Path(agent_config_path))

    observation_payload = json.loads((config_root / "observation_config.json").read_text(encoding="utf-8"))
    schedules_all = load_observation_config(config_root / "observation_config.json")
    managed_hosts = {}
    for item in agent_payload["managed_hosts"]:
        if item.get("enrollment") != "MANAGED":
            continue
        name = f"managed.{item['host_id']}"
        source_cfg = observation_payload["sources"].get(name, {})
        operations = tuple(source_cfg.get("operations") or ("uptime",))
        managed_hosts[str(item["host_id"])] = operations
    if not managed_hosts:
        raise ValueError("no MANAGED hosts configured for observation")
    source_names = {"wifi.presence", *(f"managed.{host}" for host in managed_hosts)}
    schedules = {name: schedules_all[name] for name in source_names}
    wifi_cfg = observation_payload["sources"]["wifi.presence"]
    wifi = WifiPresenceSource(
        wifi_interface,
        scanner=scanner,
        presence_window_s=float(wifi_cfg["presence_window_seconds"]),
        max_devices=int(wifi_cfg["max_devices"]),
        repository=PresenceRepository(state_dir / "presence.json", max_devices=int(wifi_cfg["max_devices"])),
    )
    composition = build_affective_composition(
        config_root=config_root,
        state_dir=state_dir,
        now=_utc_now,
        id_factory=lambda: str(uuid.uuid4()),
    )
    bus = StimulusBus(capacity=128)
    journal_path = state_dir / "stimulus.jsonl"
    runtime = build_dual_zone_runtime(
        wifi_source=wifi,
        managed_read_service=service,
        managed_hosts=managed_hosts,
        bus=bus,
        journal=lambda stimulus: append_stimulus(
            journal_path, stimulus, {"expected_sha": expected_sha}
        ),
        schedule=schedules,
        accepted_stimulus_sink=composition.processar,
    )
    listener = interaction_listener or InteractionDatagramListener(
        state_dir / "affective-interaction.sock",
        composition.runtime_visual.atualizar_interacao,
    )
    return ObservationDaemonContext(
        runtime, bus, composition, listener,
        state_dir / "observation-affective-health.json",
        expected_sha,
    )

def _drain_bus(bus: StimulusBus) -> None:
    while bus.poll() is not None:
        pass


def _health_payload(context: ObservationDaemonContext) -> dict:
    runtime_errors = context.runtime.errors()
    composition_errors = context.composition.errors()
    interaction_errors = context.interaction_listener.errors()
    status = "degraded" if runtime_errors or composition_errors or interaction_errors else "healthy"
    return {
        "schema_version": 1,
        "status": status,
        "expected_sha": context.expected_sha,
        "last_cycle_at": context.last_cycle_at,
        "bus_metrics": asdict(context.bus.metrics()),
        "restoration": dict(context.composition.restoration),
        "errors": {
            "observation": list(runtime_errors[-16:]),
            "affective": list(composition_errors[-16:]),
            "interaction": list(interaction_errors[-16:]),
        },
        "visual_present": (context.health_path.parent / "visual-state.json").is_file(),
    }


def run_daemon_cycle(context: ObservationDaemonContext) -> float:
    delay = context.runtime.run_scheduled_cycle()
    timeout = min(1.0, max(0.01, float(delay)))
    context.interaction_listener.run_once(timeout_s=timeout)
    _drain_bus(context.bus)
    context.last_cycle_at = _utc_now()
    _atomic_json(context.health_path, _health_payload(context))
    return delay

def resolve_wifi_interface(env=None, sys_class_net: Path = Path("/sys/class/net")) -> str:
    values = os.environ if env is None else env
    configured = str(values.get("ATLAS_WIFI_INTERFACE", "")).strip()
    if configured:
        return configured
    root = Path(sys_class_net)
    if root.is_dir():
        candidates = sorted(
            item.name for item in root.iterdir()
            if item.is_dir() and (item / "wireless").exists()
        )
        if candidates:
            return candidates[0]
    raise RuntimeError("wifi interface not configured or discoverable")


def run_observation_daemon(context: ObservationDaemonContext, stop_event) -> None:
    try:
        while not stop_event.is_set():
            run_daemon_cycle(context)
    finally:
        context.close()


def main() -> int:
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    expected_sha = os.environ.get("ATLAS_EXPECTED_SHA") or None
    context = build_observation_context(
        wifi_interface=resolve_wifi_interface(),
        expected_sha=expected_sha,
    )
    print("ATLAS_AFFECTIVE_OBSERVATION_DAEMON_READY", flush=True)
    run_observation_daemon(context, stop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
