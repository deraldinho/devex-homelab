import unittest

from infrastructure.pentium.agent.actions.x99_status import collect_x99_status
from infrastructure.pentium.agent.managed_read import ManagedReadOperation


class FakeManagedRead:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def read(self, host_id, operation):
        self.calls.append((host_id, operation))
        return self.result


class X99StatusTests(unittest.TestCase):
    def test_healthy_payload_is_reduced_from_typed_read(self):
        service = FakeManagedRead({
            "status": "healthy",
            "host": "x99",
            "operation": "uptime",
            "hostname": "x99",
            "user": "deral",
            "last_boot": "2026-09-03T12:00:00Z",
            "uptime_seconds": 3600,
        })
        result = collect_x99_status(service)
        self.assertEqual(result["status"], "healthy")
        self.assertEqual(result["hostname"], "x99")
        self.assertEqual(result["uptime_seconds"], 3600)
        self.assertEqual(service.calls, [("x99", ManagedReadOperation.UPTIME)])

    def test_degraded_typed_read_is_preserved(self):
        service = FakeManagedRead({
            "status": "degraded",
            "host": "x99",
            "operation": "uptime",
            "error": "ssh-failed",
            "detail": "permission denied",
        })
        result = collect_x99_status(service)
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["error"], "ssh-failed")

    def test_unexpected_hostname_is_degraded(self):
        service = FakeManagedRead({
            "status": "healthy",
            "host": "x99",
            "operation": "uptime",
            "hostname": "other",
            "user": "deral",
            "last_boot": "2026-09-03T12:00:00Z",
            "uptime_seconds": 3600,
        })
        result = collect_x99_status(service)
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["error"], "unexpected-host")


if __name__ == "__main__":
    unittest.main()
