import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from actions.x99_status import collect_x99_status
from ssh_transport import SshResult, SshTarget


class FakeTransport:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, target, remote_command):
        self.calls.append((target, remote_command))
        return self.result


class X99StatusTests(unittest.TestCase):
    def setUp(self):
        self.target = SshTarget(
            user="deral",
            host="100.101.23.111",
            identity_file=Path("/tmp/key"),
            known_hosts_file=Path("/tmp/known_hosts"),
        )
    def test_healthy_payload_is_reduced(self):
        payload = {
            "hostname": "x99",
            "user": "deral",
            "last_boot": "2026-09-03T12:00:00Z",
            "uptime_seconds": 3600,
        }
        transport = FakeTransport(SshResult(0, json.dumps(payload), ""))
        result = collect_x99_status(transport, self.target)
        self.assertEqual(result["status"], "healthy")
        self.assertEqual(result["hostname"], "x99")
        self.assertEqual(result["user"], "deral")
        self.assertEqual(result["uptime_seconds"], 3600)

    def test_ssh_failure_is_degraded(self):
        transport = FakeTransport(SshResult(255, "", "permission denied", "ssh-failed"))
        result = collect_x99_status(transport, self.target)
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["error"], "ssh-failed")

    def test_invalid_json_is_degraded(self):
        transport = FakeTransport(SshResult(0, "not-json", ""))
        result = collect_x99_status(transport, self.target)
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["error"], "invalid-json")

    def test_unexpected_hostname_is_degraded(self):
        payload = {
            "hostname": "other",
            "user": "deral",
            "last_boot": "2026-09-03T12:00:00Z",
            "uptime_seconds": 3600,
        }
        transport = FakeTransport(SshResult(0, json.dumps(payload), ""))
        result = collect_x99_status(transport, self.target)
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["error"], "unexpected-host")


if __name__ == "__main__":
    unittest.main()
