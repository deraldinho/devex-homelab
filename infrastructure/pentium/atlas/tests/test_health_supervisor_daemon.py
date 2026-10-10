import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from infrastructure.pentium.atlas.health_probes import ProbeResult
from infrastructure.pentium.atlas.health_supervisor import AtlasHealthSupervisor, HealthSnapshotPublisher
from infrastructure.pentium.atlas.health_supervisor_daemon import (
    HealthSupervisorOwner,
    ServiceProbeBundle,
    load_health_supervisor_config,
)
from infrastructure.pentium.atlas.health_supervisor_model import ComponentHealthState


NOW = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)


class Probe:
    def __init__(self, state, *, ok=None, reason="probe"):
        self.state = state
        self.ok = state is ComponentHealthState.HEALTHY if ok is None else ok
        self.reason = reason
        self.calls = 0

    def probe(self):
        self.calls += 1
        return ProbeResult(
            self.ok,
            self.state,
            NOW.isoformat(),
            self.reason,
            (f"probe:{self.reason}",),
            {},
        )


class HealthSupervisorDaemonTests(unittest.TestCase):
    def test_owner_combines_process_and_functional_health_and_publishes_snapshot(self):
        process = Probe(ComponentHealthState.HEALTHY, reason="systemd")
        functional = Probe(ComponentHealthState.DISCONNECTED, ok=False, reason="gateway")
        bundle = ServiceProbeBundle(
            component_id="atlas-discord.service",
            host="pentium",
            expected_state="running",
            required=True,
            process_probe=process,
            functional_probe=functional,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            owner = HealthSupervisorOwner(
                AtlasHealthSupervisor(),
                HealthSnapshotPublisher(root / "health-supervisor.json", root / "health-events.jsonl"),
                (bundle,),
                poll_interval_s=15,
                now=lambda: NOW,
            )
            snapshot = owner.run_once()
            self.assertEqual(ComponentHealthState.DISCONNECTED, snapshot.state)
            payload = json.loads((root / "health-supervisor.json").read_text(encoding="utf-8"))
            self.assertEqual("disconnected", payload["state"])
            self.assertEqual(1, process.calls)
            self.assertEqual(1, functional.calls)

    def test_expected_paused_bundle_remains_intentionally_paused(self):
        paused = Probe(ComponentHealthState.PAUSED_INTENTIONALLY, reason="expected_paused")
        bundle = ServiceProbeBundle(
            component_id="atlas-voice.service",
            host="pentium",
            expected_state="paused",
            required=True,
            process_probe=paused,
            functional_probe=paused,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            owner = HealthSupervisorOwner(
                AtlasHealthSupervisor(),
                HealthSnapshotPublisher(root / "health.json", root / "events.jsonl"),
                (bundle,),
                poll_interval_s=15,
                now=lambda: NOW,
            )
            snapshot = owner.run_once()
            self.assertEqual(ComponentHealthState.HEALTHY, snapshot.state)
            self.assertEqual(
                ComponentHealthState.PAUSED_INTENTIONALLY,
                snapshot.components[0].state,
            )

    def test_config_loader_validates_feature_flags_and_interval(self):
        payload = {
            "schema_version": 1,
            "features": {"health_supervisor_v1": True, "self_healing_v1": False},
            "poll_interval_s": 15,
            "components": {},
            "managed_hosts": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            config = load_health_supervisor_config(path)
        self.assertTrue(config["features"]["health_supervisor_v1"])
        self.assertFalse(config["features"]["self_healing_v1"])
        self.assertEqual(15.0, config["poll_interval_s"])

    def test_config_loader_rejects_invalid_schema_and_nonpositive_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({
                "schema_version": 9,
                "features": {},
                "poll_interval_s": 0,
                "components": {},
                "managed_hosts": {},
            }), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_health_supervisor_config(path)


if __name__ == "__main__":
    unittest.main()
