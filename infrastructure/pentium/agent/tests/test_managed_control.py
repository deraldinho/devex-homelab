from pathlib import Path
import unittest

from infrastructure.pentium.agent.managed_control import (
    ControlAuthorization,
    ManagedControlOperation,
    ManagedControlService,
)
from infrastructure.pentium.agent.managed_inventory import ManagedHost, ManagedInventory
from infrastructure.pentium.agent.ssh_transport import SshResult


class FakeTransport:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or SshResult(0, "", "")

    def run(self, target, command):
        self.calls.append((target, command))
        return self.result


class FakeAudit:
    def __init__(self, *, fail=False):
        self.records = []
        self.fail = fail

    def append(self, record):
        if self.fail:
            raise OSError("audit unavailable")
        self.records.append(record)


class ManagedControlTests(unittest.TestCase):
    def host(self, *, platform="linux"):
        return ManagedHost(
            host_id="x99", enrollment="MANAGED", user="deral", host="10.0.0.9",
            identity_file=Path("/keys/x99"), known_hosts_file=Path("/ssh/known_hosts"),
            platform=platform, allowed_reads=frozenset({"uptime"}),
            allowed_controls=frozenset({"start_service", "stop_service", "restart_service", "restart_container", "reboot_host"}),
            allowed_services=frozenset({"docker"}),
            allowed_containers=frozenset({"atlas-worker"}),
        )

    def service(self, host=None, result=None, *, audit_fail=False):
        transport = FakeTransport(result)
        audit = FakeAudit(fail=audit_fail)
        inventory = ManagedInventory([host or self.host()])
        return ManagedControlService(inventory, transport, audit), transport, audit

    def auth(self, operation, *, target=None, authorized=True, human_confirmed=False):
        return ControlAuthorization(
            authorized=authorized,
            host_id="x99",
            operation=operation,
            target=target,
            human_confirmed=human_confirmed,
            reason="test",
        )

    def test_denied_authorization_never_reaches_ssh(self):
        service, transport, _ = self.service()
        with self.assertRaises(PermissionError):
            service.execute(self.auth(ManagedControlOperation.RESTART_SERVICE, target="docker", authorized=False))
        self.assertEqual(transport.calls, [])

    def test_service_target_outside_host_allowlist_never_reaches_ssh(self):
        service, transport, _ = self.service()
        with self.assertRaises(PermissionError):
            service.execute(self.auth(ManagedControlOperation.RESTART_SERVICE, target="sshd"))
        self.assertEqual(transport.calls, [])

    def test_reboot_requires_human_confirmation_before_ssh(self):
        service, transport, _ = self.service()
        with self.assertRaises(PermissionError):
            service.execute(self.auth(ManagedControlOperation.REBOOT_HOST))
        self.assertEqual(transport.calls, [])

    def test_pre_audit_failure_blocks_ssh(self):
        service, transport, _ = self.service(audit_fail=True)
        with self.assertRaises(OSError):
            service.execute(self.auth(ManagedControlOperation.RESTART_SERVICE, target="docker"))
        self.assertEqual(transport.calls, [])

    def test_linux_restart_uses_fixed_systemctl_command_and_audits(self):
        service, transport, audit = self.service()
        result = service.execute(self.auth(ManagedControlOperation.RESTART_SERVICE, target="docker"))
        self.assertEqual(result["status"], "success")
        self.assertEqual(transport.calls[0][1], "systemctl restart docker")
        self.assertEqual([r.phase for r in audit.records], ["attempt", "result"])

    def test_restart_container_requires_exact_allowlist_and_uses_fixed_docker_command(self):
        service, transport, _ = self.service()
        result = service.execute(self.auth(ManagedControlOperation.RESTART_CONTAINER, target="atlas-worker"))
        self.assertEqual("success", result["status"])
        self.assertEqual("docker restart atlas-worker", transport.calls[0][1])
        blocked, blocked_transport, _ = self.service()
        with self.assertRaises(PermissionError):
            blocked.execute(self.auth(ManagedControlOperation.RESTART_CONTAINER, target="other-container"))
        self.assertEqual([], blocked_transport.calls)

    def test_ssh_failure_is_audited_as_degraded(self):
        failed = SshResult(255, "", "denied", "ssh-failed")
        service, _, audit = self.service(result=failed)
        result = service.execute(self.auth(ManagedControlOperation.RESTART_SERVICE, target="docker"))
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(audit.records[-1].status, "degraded")

    def test_windows_start_uses_fixed_powershell_command(self):
        service, transport, _ = self.service(self.host(platform="windows"))
        result = service.execute(self.auth(ManagedControlOperation.START_SERVICE, target="docker"))
        self.assertEqual(result["status"], "success")
        self.assertEqual(
            transport.calls[0][1],
            "powershell.exe -NoProfile -NonInteractive -Command \"Start-Service -Name 'docker'\"",
        )

    def test_no_public_arbitrary_shell_api(self):
        service, _, _ = self.service()
        self.assertFalse(hasattr(service, "run_shell"))
        self.assertFalse(hasattr(service, "execute_shell"))


if __name__ == "__main__":
    unittest.main()
