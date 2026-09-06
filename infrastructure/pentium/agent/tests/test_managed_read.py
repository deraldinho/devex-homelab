import json
import unittest
from pathlib import Path

from infrastructure.pentium.agent.managed_inventory import ManagedHost, ManagedInventory
from infrastructure.pentium.agent.managed_read import ManagedReadOperation, ManagedReadService
from infrastructure.pentium.agent.ssh_transport import SshResult


class FakeTransport:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, target, command):
        self.calls.append((target, command))
        return self.result


class ManagedReadTests(unittest.TestCase):
    def make_host(self, allowed=frozenset({"uptime", "memory"})):
        return ManagedHost(
            host_id="x99", enrollment="MANAGED", user="deral",
            host="192.168.88.20", identity_file=Path("/keys/x99"),
            known_hosts_file=Path("/ssh/known_hosts"), platform="windows",
            allowed_reads=allowed,
        )

    def make_service(self, result, allowed=frozenset({"uptime", "memory"})):
        transport = FakeTransport(result)
        service = ManagedReadService(ManagedInventory([self.make_host(allowed)]), transport)
        return service, transport

    def test_uptime_uses_fixed_command_and_normalizes_payload(self):
        service, transport = self.make_service(
            SshResult(0, json.dumps({"uptime_seconds": 3600}), "")
        )
        result = service.read("x99", ManagedReadOperation.UPTIME)
        self.assertEqual(result, {"status": "healthy", "host": "x99", "operation": "uptime", "uptime_seconds": 3600})
        self.assertEqual(len(transport.calls), 1)
        self.assertNotIn("3600", transport.calls[0][1])

    def test_memory_normalizes_typed_payload(self):
        service, _ = self.make_service(
            SshResult(0, json.dumps({"total_bytes": 1000, "available_bytes": 250}), "")
        )
        result = service.read("x99", ManagedReadOperation.MEMORY)
        self.assertEqual(result["memory"]["total_bytes"], 1000)
        self.assertEqual(result["memory"]["available_bytes"], 250)

    def test_operation_outside_host_allowlist_fails_before_transport(self):
        service, transport = self.make_service(SshResult(0, "{}", ""), allowed=frozenset({"uptime"}))
        with self.assertRaises(PermissionError):
            service.read("x99", ManagedReadOperation.CPU)
        self.assertEqual(transport.calls, [])

    def test_unknown_host_fails_before_transport(self):
        service, transport = self.make_service(SshResult(0, "{}", ""))
        with self.assertRaises(LookupError):
            service.read("ghost", ManagedReadOperation.UPTIME)
        self.assertEqual(transport.calls, [])

    def test_ssh_failure_is_degraded_not_host_health(self):
        service, _ = self.make_service(SshResult(255, "", "denied", "ssh-failed"))
        result = service.read("x99", ManagedReadOperation.UPTIME)
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["error"], "ssh-failed")
        self.assertNotIn("health", result)

    def test_catalog_exposes_no_arbitrary_shell_method(self):
        public = {name for name in dir(ManagedReadService) if not name.startswith("_")}
        self.assertNotIn("run_shell", public)
        self.assertNotIn("exec", public)
        self.assertEqual(
            {operation.value for operation in ManagedReadOperation},
            {"cpu", "memory", "disk", "uptime", "temperature", "services", "processes", "network", "containers", "logs"},
        )


if __name__ == "__main__":
    unittest.main()
