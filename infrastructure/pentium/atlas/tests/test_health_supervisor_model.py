import unittest
from dataclasses import fields

from infrastructure.pentium.atlas.state_model import TechnicalState
from infrastructure.pentium.atlas.health_supervisor_model import (
    ComponentHealth,
    ComponentHealthState,
    HealthDimension,
    map_technical_state,
)


class HealthSupervisorModelTests(unittest.TestCase):
    def test_component_health_state_has_canonical_values(self):
        self.assertEqual(
            {
                "HEALTHY", "DEGRADED", "STALE", "DISCONNECTED",
                "FAILED", "RECOVERING", "PAUSED_INTENTIONALLY", "UNKNOWN",
            },
            {item.name for item in ComponentHealthState},
        )

    def test_component_health_requires_canonical_dimensions_and_evidence(self):
        model_fields = {item.name for item in fields(ComponentHealth)}
        self.assertTrue({
            "component_id", "host", "expected_state", "process_state",
            "functional_state", "freshness", "dependency_state",
            "observed_at", "evidence_refs",
        }.issubset(model_fields))
        health = ComponentHealth(
            component_id="atlas-discord.service",
            host="pentium",
            expected_state="running",
            process_state=HealthDimension(ComponentHealthState.HEALTHY, "systemd_active"),
            functional_state=HealthDimension(ComponentHealthState.HEALTHY, "gateway_connected"),
            freshness=HealthDimension(ComponentHealthState.HEALTHY, "fresh"),
            dependency_state=HealthDimension(ComponentHealthState.HEALTHY, "discord_reachable"),
            observed_at="2026-10-09T12:00:00+00:00",
            evidence_refs=("runtime:discord-gateway-health.json",),
        )
        self.assertEqual("atlas-discord.service", health.component_id)
        self.assertEqual(("runtime:discord-gateway-health.json",), health.evidence_refs)

    def test_component_health_rejects_naive_timestamp(self):
        with self.assertRaises(ValueError):
            ComponentHealth(
                component_id="atlas-discord.service",
                host="pentium",
                expected_state="running",
                process_state=HealthDimension(ComponentHealthState.HEALTHY, "ok"),
                functional_state=HealthDimension(ComponentHealthState.HEALTHY, "ok"),
                freshness=HealthDimension(ComponentHealthState.HEALTHY, "ok"),
                dependency_state=HealthDimension(ComponentHealthState.HEALTHY, "ok"),
                observed_at="2026-10-09T12:00:00",
            )

    def test_legacy_healthy_active_and_recovered_map_to_healthy(self):
        for state in (TechnicalState.HEALTHY, TechnicalState.ACTIVE, TechnicalState.RECOVERED):
            self.assertIs(ComponentHealthState.HEALTHY, map_technical_state(state))

    def test_legacy_busy_degraded_and_stressed_map_to_degraded(self):
        for state in (TechnicalState.BUSY, TechnicalState.DEGRADED, TechnicalState.STRESSED):
            self.assertIs(ComponentHealthState.DEGRADED, map_technical_state(state))

    def test_legacy_critical_maps_to_failed(self):
        self.assertIs(ComponentHealthState.FAILED, map_technical_state(TechnicalState.CRITICAL))

    def test_health_dimension_requires_canonical_state(self):
        with self.assertRaises(TypeError):
            HealthDimension("healthy", "invalid")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
