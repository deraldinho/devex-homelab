import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from infrastructure.pentium.agent.managed_inventory import (
    ManagedHost,
    ManagedInventory,
    UnknownManagedHostError,
)
from infrastructure.pentium.atlas.health_probes import ProbeResult
from infrastructure.pentium.atlas.health_supervisor_model import ComponentHealthState
from infrastructure.pentium.atlas.host_adapters import (
    ManagedHostAdapter,
    PentiumHostAdapter,
)


NOW = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)


class FakeReadService:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def read(self, host_id, operation):
        self.calls.append((host_id, operation.value))
        if isinstance(self.payload, Exception):
            raise self.payload
        return dict(self.payload)


def managed_inventory(tmp, *, host_id="x99", platform="windows", allowed_reads=("uptime",)):
    return ManagedInventory([
        ManagedHost(
            host_id=host_id,
            enrollment="MANAGED",
            user="operator",
            host="100.64.0.10",
            identity_file=Path(tmp) / "id",
            known_hosts_file=Path(tmp) / "known",
            platform=platform,
            allowed_reads=frozenset(allowed_reads),
        )
    ])


class HostAdapterTests(unittest.TestCase):
    def test_pentium_observes_local_target_without_ssh(self):
        calls = []
        def probe(target):
            calls.append(target)
            return ProbeResult(
                True,
                ComponentHealthState.HEALTHY,
                NOW.isoformat(),
                "local_ok",
                (f"local:{target}",),
                {"dimension": "process"},
            )
        result = PentiumHostAdapter(probe, clock=lambda: NOW).observe("atlas-discord.service")
        self.assertEqual(["atlas-discord.service"], calls)
        self.assertEqual("pentium", result.host)
        self.assertEqual("linux", result.platform)
        self.assertEqual("atlas-discord.service", result.target)
        self.assertEqual(ComponentHealthState.HEALTHY, result.state)
        self.assertEqual(("local:atlas-discord.service",), result.evidence_refs)

    def test_managed_adapter_calls_managed_read_service_not_ssh(self):
        with tempfile.TemporaryDirectory() as tmp:
            inventory = managed_inventory(tmp)
            reads = FakeReadService({"status": "healthy", "host": "x99", "operation": "uptime", "uptime_seconds": 10})
            result = ManagedHostAdapter("x99", inventory, reads, clock=lambda: NOW).observe("uptime")
            self.assertEqual([("x99", "uptime")], reads.calls)
            self.assertEqual("x99", result.host)
            self.assertEqual("windows", result.platform)
            self.assertEqual(ComponentHealthState.HEALTHY, result.state)
            self.assertEqual("healthy", result.raw_status["status"])

    def test_unknown_managed_host_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            inventory = managed_inventory(tmp)
            adapter = ManagedHostAdapter("core", inventory, FakeReadService({}), clock=lambda: NOW)
            with self.assertRaises(UnknownManagedHostError):
                adapter.observe("uptime")

    def test_remote_timeout_becomes_disconnected_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            inventory = managed_inventory(tmp)
            reads = FakeReadService({
                "status": "degraded",
                "host": "x99",
                "operation": "uptime",
                "error": "timeout",
                "detail": "",
            })
            result = ManagedHostAdapter("x99", inventory, reads, clock=lambda: NOW).observe("uptime")
            self.assertEqual(ComponentHealthState.DISCONNECTED, result.state)
            self.assertFalse(result.ok)
            self.assertIn("timeout", result.reason)

    def test_read_operation_not_allowlisted_is_denied_without_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            inventory = managed_inventory(tmp, allowed_reads=("uptime",))
            reads = FakeReadService(PermissionError("read operation not allowed: services"))
            adapter = ManagedHostAdapter("x99", inventory, reads, clock=lambda: NOW)
            with self.assertRaises(PermissionError):
                adapter.observe("services")
            self.assertEqual([("x99", "services")], reads.calls)

    def test_managed_observation_contains_target_time_evidence_and_reduced_raw_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            inventory = managed_inventory(tmp, host_id="core", platform="linux")
            reads = FakeReadService({
                "status": "healthy",
                "host": "core",
                "operation": "uptime",
                "uptime_seconds": 42,
            })
            result = ManagedHostAdapter("core", inventory, reads, clock=lambda: NOW).observe("uptime")
            self.assertEqual("core", result.host)
            self.assertEqual("uptime", result.target)
            self.assertEqual("linux", result.platform)
            self.assertEqual(NOW.isoformat(), result.observed_at)
            self.assertEqual(("managed-read:core:uptime",), result.evidence_refs)
            self.assertEqual(42, result.raw_status["uptime_seconds"])


if __name__ == "__main__":
    unittest.main()
