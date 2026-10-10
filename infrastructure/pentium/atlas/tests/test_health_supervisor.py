import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.health_supervisor import (
    AtlasHealthSupervisor,
    HealthSnapshotPublisher,
)
from infrastructure.pentium.atlas.health_supervisor_model import (
    ComponentHealth,
    ComponentHealthState,
    HealthDimension,
)


def dim(state, reason=""):
    return HealthDimension(state, reason)


def component(
    component_id="svc",
    *,
    process=ComponentHealthState.HEALTHY,
    functional=ComponentHealthState.HEALTHY,
    freshness=ComponentHealthState.HEALTHY,
    dependency=ComponentHealthState.HEALTHY,
    expected_state="running",
    required=True,
):
    return ComponentHealth(
        component_id=component_id,
        host="pentium",
        expected_state=expected_state,
        process_state=dim(process, "process"),
        functional_state=dim(functional, "functional"),
        freshness=dim(freshness, "freshness"),
        dependency_state=dim(dependency, "dependency"),
        observed_at="2026-10-09T12:00:00+00:00",
        evidence_refs=(f"evidence:{component_id}",),
        required=required,
    )


class HealthSupervisorTests(unittest.TestCase):
    def test_expected_paused_component_is_paused_intentionally(self):
        snapshot = AtlasHealthSupervisor().evaluate(
            (component(expected_state="paused", process=ComponentHealthState.FAILED),),
            "2026-10-09T12:00:01+00:00",
        )
        self.assertEqual(ComponentHealthState.PAUSED_INTENTIONALLY, snapshot.components[0].state)
        self.assertEqual(ComponentHealthState.HEALTHY, snapshot.state)

    def test_active_process_with_disconnected_function_is_disconnected(self):
        snapshot = AtlasHealthSupervisor().evaluate(
            (component(functional=ComponentHealthState.DISCONNECTED),),
            "2026-10-09T12:00:01+00:00",
        )
        self.assertEqual(ComponentHealthState.DISCONNECTED, snapshot.components[0].state)
        self.assertEqual(ComponentHealthState.DISCONNECTED, snapshot.state)

    def test_stale_freshness_prevents_healthy(self):
        snapshot = AtlasHealthSupervisor().evaluate(
            (component(freshness=ComponentHealthState.STALE),),
            "2026-10-09T12:00:01+00:00",
        )
        self.assertEqual(ComponentHealthState.STALE, snapshot.components[0].state)

    def test_failed_dependency_degrades_component(self):
        snapshot = AtlasHealthSupervisor().evaluate(
            (component(dependency=ComponentHealthState.FAILED),),
            "2026-10-09T12:00:01+00:00",
        )
        self.assertIn(
            snapshot.components[0].state,
            {ComponentHealthState.DEGRADED, ComponentHealthState.FAILED},
        )
        self.assertNotEqual(ComponentHealthState.HEALTHY, snapshot.components[0].state)

    def test_all_dimensions_healthy_is_healthy(self):
        snapshot = AtlasHealthSupervisor().evaluate(
            (component(),),
            "2026-10-09T12:00:01+00:00",
        )
        self.assertEqual(ComponentHealthState.HEALTHY, snapshot.state)
        self.assertEqual(ComponentHealthState.HEALTHY, snapshot.components[0].state)

    def test_unknown_optional_component_does_not_improve_or_degrade_required_aggregate(self):
        snapshot = AtlasHealthSupervisor().evaluate(
            (
                component("required", functional=ComponentHealthState.DEGRADED),
                component("optional", functional=ComponentHealthState.UNKNOWN, required=False),
            ),
            "2026-10-09T12:00:01+00:00",
        )
        self.assertEqual(ComponentHealthState.DEGRADED, snapshot.state)

    def test_publisher_writes_atomic_snapshot_and_only_transition_events(self):
        supervisor = AtlasHealthSupervisor()
        healthy = supervisor.evaluate((component(),), "2026-10-09T12:00:01+00:00")
        degraded = supervisor.evaluate(
            (component(functional=ComponentHealthState.DEGRADED),),
            "2026-10-09T12:00:02+00:00",
        )
        recovered = supervisor.evaluate((component(),), "2026-10-09T12:00:03+00:00")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot_path = root / "health-supervisor.json"
            events_path = root / "health-events.jsonl"
            publisher = HealthSnapshotPublisher(snapshot_path, events_path)

            publisher.publish(healthy)
            publisher.publish(healthy)
            publisher.publish(degraded)
            publisher.publish(recovered)

            self.assertFalse((root / "health-supervisor.json.tmp").exists())
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            self.assertEqual("healthy", payload["state"])
            events = [
                json.loads(line)
                for line in events_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(3, len(events))
            self.assertEqual(["healthy", "degraded", "healthy"], [e["state"] for e in events])
            self.assertEqual("recovered", events[-1]["transition"])


if __name__ == "__main__":
    unittest.main()
