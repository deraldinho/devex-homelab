import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from infrastructure.pentium.atlas.health_probes import (
    CognitiveSnapshotProbe,
    DashboardHttpProbe,
    DiscordGatewayProbe,
    JsonTimestampStatusProbe,
    ObservationJournalProbe,
    SystemdUserProbe,
)
from infrastructure.pentium.atlas.health_supervisor_model import ComponentHealthState


NOW = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)


class HealthProbeTests(unittest.TestCase):
    def test_systemd_active_is_only_process_health_evidence(self):
        calls = []
        def runner(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, stdout="active\n", stderr="")
        result = SystemdUserProbe("atlas-discord.service", runner=runner, clock=lambda: NOW).probe()
        self.assertTrue(result.ok)
        self.assertEqual(ComponentHealthState.HEALTHY, result.state)
        self.assertEqual("process", result.metrics["dimension"])
        self.assertIn("systemd_active", result.reason)
        self.assertEqual(["systemctl", "--user", "is-active", "atlas-discord.service"], calls[0])

    def test_systemd_expected_paused_does_not_require_running_process(self):
        calls = []
        result = SystemdUserProbe(
            "atlas-voice.service",
            expected_state="paused",
            runner=lambda *a, **k: calls.append(a),
            clock=lambda: NOW,
        ).probe()
        self.assertEqual(ComponentHealthState.PAUSED_INTENTIONALLY, result.state)
        self.assertFalse(calls)

    def test_discord_disconnected_health_file_is_disconnected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "discord-gateway-health.json"
            path.write_text(json.dumps({
                "schema_version": 1,
                "state": "disconnected",
                "connected": False,
                "reason": "socket_closed",
                "updated_at": "2026-10-09T11:59:50+00:00",
            }), encoding="utf-8")
            result = DiscordGatewayProbe(path, max_age_s=30, clock=lambda: NOW).probe()
            self.assertFalse(result.ok)
            self.assertEqual(ComponentHealthState.DISCONNECTED, result.state)

    def test_discord_old_health_file_is_stale_even_if_connected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "discord-gateway-health.json"
            path.write_text(json.dumps({
                "schema_version": 1,
                "state": "connected",
                "connected": True,
                "reason": "ready",
                "updated_at": "2026-10-09T11:58:00+00:00",
            }), encoding="utf-8")
            result = DiscordGatewayProbe(path, max_age_s=30, clock=lambda: NOW).probe()
            self.assertFalse(result.ok)
            self.assertEqual(ComponentHealthState.STALE, result.state)

    def test_cognitive_snapshot_older_than_bound_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cognitive-runtime.json"
            path.write_text(json.dumps({"generated_at": "2026-10-09T11:58:00+00:00"}), encoding="utf-8")
            result = CognitiveSnapshotProbe(path, max_age_s=30, clock=lambda: NOW).probe()
            self.assertEqual(ComponentHealthState.STALE, result.state)

    def test_json_status_probe_uses_last_cycle_timestamp_and_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "observation-affective-health.json"
            path.write_text(json.dumps({
                "status": "healthy",
                "last_cycle_at": "2026-10-09T11:59:50+00:00",
            }), encoding="utf-8")
            result = JsonTimestampStatusProbe(
                path,
                timestamp_field="last_cycle_at",
                max_age_s=30,
                status_field="status",
                healthy_values=("healthy",),
                clock=lambda: NOW,
            ).probe()
            self.assertTrue(result.ok)
            self.assertEqual(ComponentHealthState.HEALTHY, result.state)

            path.write_text(json.dumps({
                "status": "degraded",
                "last_cycle_at": "2026-10-09T11:59:55+00:00",
            }), encoding="utf-8")
            degraded = JsonTimestampStatusProbe(
                path,
                timestamp_field="last_cycle_at",
                max_age_s=30,
                status_field="status",
                healthy_values=("healthy",),
                clock=lambda: NOW,
            ).probe()
            self.assertFalse(degraded.ok)
            self.assertEqual(ComponentHealthState.DEGRADED, degraded.state)

    def test_observation_journal_not_progressing_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stimulus.jsonl"
            path.write_text('{"id":"s1"}\n', encoding="utf-8")
            old_epoch = NOW.timestamp() - 120
            os.utime(path, (old_epoch, old_epoch))
            result = ObservationJournalProbe(path, max_age_s=30, clock=lambda: NOW).probe()
            self.assertEqual(ComponentHealthState.STALE, result.state)

    def test_dashboard_non_2xx_is_degraded(self):
        result = DashboardHttpProbe(
            "http://127.0.0.1:8080/api/status",
            getter=lambda url, timeout: (503, {"status": "down"}),
            clock=lambda: NOW,
        ).probe()
        self.assertFalse(result.ok)
        self.assertEqual(ComponentHealthState.DEGRADED, result.state)

    def test_dashboard_unparseable_payload_is_degraded(self):
        result = DashboardHttpProbe(
            "http://127.0.0.1:8080/api/status",
            getter=lambda url, timeout: (200, "not-json"),
            clock=lambda: NOW,
        ).probe()
        self.assertFalse(result.ok)
        self.assertEqual(ComponentHealthState.DEGRADED, result.state)


if __name__ == "__main__":
    unittest.main()
