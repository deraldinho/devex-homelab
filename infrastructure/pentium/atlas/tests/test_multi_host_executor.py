import unittest
from pathlib import Path

from infrastructure.pentium.agent.managed_control import ManagedControlService
from infrastructure.pentium.agent.managed_inventory import (
    ManagedHost,
    ManagedInventory,
    UnknownManagedHostError,
)
from infrastructure.pentium.agent.ssh_transport import SshResult
from infrastructure.pentium.atlas.autonomy_executor import VerificationFailedError
from infrastructure.pentium.atlas.multi_host_executor import MultiHostCapabilityExecutor


class FakeTransport:
    def __init__(self):
        self.calls = []

    def run(self, target, command):
        self.calls.append((target, command))
        return SshResult(0, "", "")


class FakeAudit:
    def __init__(self):
        self.records = []

    def append(self, record):
        self.records.append(record)


class FakeLocalExecutor:
    def __init__(self):
        self.calls = []

    def __call__(self, capability, arguments, plan, action):
        self.calls.append((capability, dict(arguments)))
        return None


def host(host_id, *, platform):
    return ManagedHost(
        host_id=host_id,
        enrollment="MANAGED",
        user="operator",
        host=f"100.64.0.{10 if host_id == 'x99' else 11}",
        identity_file=Path(f"/keys/{host_id}"),
        known_hosts_file=Path(f"/known/{host_id}"),
        platform=platform,
        allowed_reads=frozenset({"uptime"}),
        allowed_controls=frozenset({
            "restart_service", "restart_container", "reboot_host",
        }),
        allowed_services=frozenset({"AtlasWorker" if platform == "windows" else "atlas-worker.service"}),
        allowed_containers=frozenset({"atlas-container"}),
    )


class MultiHostExecutorTests(unittest.TestCase):
    def setUp(self):
        self.inventory = ManagedInventory([
            host("x99", platform="windows"),
            host("core", platform="linux"),
        ])
        self.transport = FakeTransport()
        self.control = ManagedControlService(self.inventory, self.transport, FakeAudit())
        self.local = FakeLocalExecutor()
        self.executed = []

    def build(self, *, verifier=lambda *args: True, confirmation_checker=lambda *args: False):
        return MultiHostCapabilityExecutor(
            self.local,
            self.control,
            self.inventory,
            verifier=verifier,
            confirmation_checker=confirmation_checker,
            on_executed=lambda capability, arguments: self.executed.append(
                (capability, dict(arguments))
            ),
        )

    def test_pentium_restart_routes_to_existing_local_executor(self):
        executor = self.build()
        result = executor(
            "restart_service",
            {"host": "pentium", "service": "atlas-dashboard.service"},
            None,
            None,
        )
        self.assertEqual(
            [("restart_service", {"host": "pentium", "service": "atlas-dashboard.service"})],
            self.local.calls,
        )
        self.assertEqual("success", result["status"])
        self.assertEqual(1, len(self.executed))

    def test_remote_service_restart_routes_through_managed_control(self):
        executor = self.build()
        result = executor(
            "restart_service",
            {"host": "core", "service": "atlas-worker.service"},
            None,
            None,
        )
        self.assertEqual("success", result["status"])
        self.assertEqual("systemctl restart atlas-worker.service", self.transport.calls[0][1])

    def test_remote_container_restart_uses_typed_managed_control(self):
        executor = self.build()
        result = executor(
            "restart_container",
            {"host": "x99", "container": "atlas-container"},
            None,
            None,
        )
        self.assertEqual("success", result["status"])
        self.assertEqual("docker restart atlas-container", self.transport.calls[0][1])

    def test_unmanaged_remote_host_fails_closed(self):
        executor = self.build()
        with self.assertRaises(UnknownManagedHostError):
            executor(
                "restart_service",
                {"host": "ghost", "service": "atlas-worker.service"},
                None,
                None,
            )

    def test_remote_target_outside_allowlist_is_denied(self):
        executor = self.build()
        with self.assertRaises(PermissionError):
            executor(
                "restart_container",
                {"host": "core", "container": "not-allowed"},
                None,
                None,
            )
        self.assertEqual([], self.transport.calls)

    def test_reboot_without_current_explicit_confirmation_is_denied(self):
        executor = self.build()
        with self.assertRaises(PermissionError):
            executor("reboot_host", {"host": "core"}, None, None)
        self.assertEqual([], self.transport.calls)

    def test_command_success_without_functional_verification_fails(self):
        executor = self.build(verifier=lambda *args: False)
        with self.assertRaises(VerificationFailedError):
            executor(
                "restart_service",
                {"host": "core", "service": "atlas-worker.service"},
                None,
                None,
            )
        self.assertEqual(1, len(self.transport.calls))
        self.assertEqual([], self.executed)

    def test_execution_history_callback_runs_only_after_verified_success(self):
        verifier_calls = []
        executor = self.build(
            verifier=lambda host, capability, arguments, result: (
                verifier_calls.append((host, capability, dict(arguments), result["status"])) or True
            )
        )
        executor(
            "restart_service",
            {"host": "x99", "service": "AtlasWorker"},
            None,
            None,
        )
        self.assertEqual(1, len(verifier_calls))
        self.assertEqual(
            [("restart_service", {"host": "x99", "service": "AtlasWorker"})],
            self.executed,
        )


if __name__ == "__main__":
    unittest.main()
