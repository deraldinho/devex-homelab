import subprocess
import unittest

from infrastructure.pentium.atlas.autonomy_executor import SafeLocalCapabilityExecutor


class AutonomyExecutorV1Tests(unittest.TestCase):
    def test_restart_allowlisted_local_service_uses_systemctl_user(self):
        calls = []
        def runner(command, **kwargs):
            calls.append((command, kwargs))
            stdout = "active\n" if "is-active" in command else ""
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
        executor = SafeLocalCapabilityExecutor(
            host="pentium",
            services=("atlas-observation.service",),
            runner=runner,
        )
        executor("restart_service", {"host":"pentium", "service":"atlas-observation.service"}, None, None)
        self.assertEqual(["systemctl", "--user", "restart", "atlas-observation.service"], calls[0][0])
        self.assertEqual(10.0, calls[0][1]["timeout"])

    def test_executor_rejects_remote_host_and_non_allowlisted_service(self):
        executor = SafeLocalCapabilityExecutor(host="pentium", services=("atlas-observation.service",))
        with self.assertRaises(PermissionError):
            executor("restart_service", {"host":"core", "service":"atlas-observation.service"}, None, None)
        with self.assertRaises(PermissionError):
            executor("restart_service", {"host":"pentium", "service":"ssh.service"}, None, None)

    def test_executor_rejects_shell_and_other_capabilities(self):
        executor = SafeLocalCapabilityExecutor(host="pentium", services=("atlas-observation.service",))
        with self.assertRaises(PermissionError):
            executor("shell", {"host":"pentium", "service":"atlas-observation.service"}, None, None)

    def test_executor_verifies_service_health_after_restart(self):
        calls = []
        def runner(command, **kwargs):
            calls.append((command, kwargs))
            if command == ["systemctl", "--user", "is-active", "atlas-observation.service"]:
                return subprocess.CompletedProcess(command, 0, stdout="active\n", stderr="")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        executor = SafeLocalCapabilityExecutor(
            host="pentium",
            services=("atlas-observation.service",),
            runner=runner,
        )
        executor("restart_service", {"host":"pentium", "service":"atlas-observation.service"}, None, None)
        self.assertEqual(["systemctl", "--user", "restart", "atlas-observation.service"], calls[0][0])
        self.assertEqual(["systemctl", "--user", "is-active", "atlas-observation.service"], calls[1][0])

    def test_executor_raises_verification_failed_if_service_fails_healthcheck(self):
        from infrastructure.pentium.atlas.autonomy_executor import VerificationFailedError
        def runner(command, **kwargs):
            if "is-active" in command:
                return subprocess.CompletedProcess(command, 3, stdout="failed\n", stderr="")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        executor = SafeLocalCapabilityExecutor(
            host="pentium",
            services=("atlas-observation.service",),
            runner=runner,
            verify_timeout_s=0.1,
            verify_poll_interval_s=0.05,
        )
        with self.assertRaises(VerificationFailedError):
            executor("restart_service", {"host":"pentium", "service":"atlas-observation.service"}, None, None)

    def test_executor_invokes_on_executed_callback(self):
        executed = []
        def runner(command, **kwargs):
            stdout = "active\n" if "is-active" in command else ""
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
        executor = SafeLocalCapabilityExecutor(
            host="pentium",
            services=("atlas-observation.service",),
            runner=runner,
            on_executed=lambda cap, args: executed.append((cap, args)),
        )
        params = {"host": "pentium", "service": "atlas-observation.service"}
        executor("restart_service", params, None, None)
        self.assertEqual([("restart_service", params)], executed)


if __name__ == "__main__":
    unittest.main()
