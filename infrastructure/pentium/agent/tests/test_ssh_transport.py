import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ssh_transport import SshTarget, SshTransport


class SshTransportTests(unittest.TestCase):
    def make_target(self, **overrides):
        values = {
            "user": "deral",
            "host": "100.101.23.111",
            "identity_file": Path("/home/deraldinho/.ssh/id_ed25519_x99"),
            "known_hosts_file": Path("/home/deraldinho/.ssh/known_hosts"),
            "connect_timeout_seconds": 5,
            "max_output_bytes": 64,
        }
        values.update(overrides)
        return SshTarget(**values)

    def test_run_builds_strict_bounded_noninteractive_argv(self):
        calls = []

        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0, stdout="ok\n", stderr="")
        target = self.make_target()
        result = SshTransport(runner=runner).run(target, "fixed-command")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "ok\n")
        argv, kwargs = calls[0]
        self.assertEqual(argv[0], "ssh")
        self.assertIn("BatchMode=yes", argv)
        self.assertIn("IdentitiesOnly=yes", argv)
        self.assertIn("StrictHostKeyChecking=yes", argv)
        self.assertIn(f"UserKnownHostsFile={target.known_hosts_file}", argv)
        self.assertIn("ConnectTimeout=5", argv)
        self.assertIn(str(target.identity_file), argv)
        self.assertEqual(argv[-2], "deral@100.101.23.111")
        self.assertEqual(argv[-1], "fixed-command")
        self.assertFalse(kwargs["shell"])
        self.assertTrue(kwargs["capture_output"])
        self.assertTrue(kwargs["text"])

    def test_timeout_becomes_structured_failure(self):
        def runner(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

        result = SshTransport(runner=runner).run(
            self.make_target(connect_timeout_seconds=3),
            "fixed-command",
        )
        self.assertEqual(result.returncode, 124)
        self.assertEqual(result.error, "timeout")

    def test_oversized_output_is_rejected_without_propagating_payload(self):
        def runner(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, stdout="x" * 128, stderr="")

        result = SshTransport(runner=runner).run(
            self.make_target(max_output_bytes=32),
            "fixed-command",
        )
        self.assertEqual(result.returncode, 125)
        self.assertEqual(result.error, "output-limit")
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_invalid_bounds_are_rejected(self):
        with self.assertRaises(ValueError):
            self.make_target(connect_timeout_seconds=0)
        with self.assertRaises(ValueError):
            self.make_target(max_output_bytes=0)


if __name__ == "__main__":
    unittest.main()
