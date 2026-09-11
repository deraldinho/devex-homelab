import unittest

from infrastructure.pentium.atlas.dual_zone_runtime import build_dual_zone_runtime
from infrastructure.pentium.atlas.observation_runtime import SourceSchedule
from infrastructure.pentium.atlas.stimulus_bus import StimulusBus
from infrastructure.pentium.atlas.stimulus_model import StimulusSeverity
from infrastructure.pentium.atlas.stimulus_sources import SourceSnapshot


class WifiSource:
    name = "wifi.presence"
    required = False

    def __init__(self, error=None):
        self.calls = 0
        self.error = error

    def poll(self):
        self.calls += 1
        if self.error:
            raise self.error
        return SourceSnapshot(self.name, "healthy", StimulusSeverity.INFO, {"zone": "WIFI_OBSERVED"})


class ManagedService:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def read(self, host_id, operation):
        self.calls.append((host_id, operation.value))
        if self.error:
            raise self.error
        return {"status": "healthy", "operation": operation.value}


def schedules():
    return {
        "wifi.presence": SourceSchedule(60, 1, 120, 0),
        "managed.x99": SourceSchedule(60, 1, 120, 0),
    }


class DualZoneRuntimeTests(unittest.TestCase):
    def build(self, wifi, managed, accepted_stimulus_sink=None):
        return build_dual_zone_runtime(
            wifi_source=wifi,
            managed_read_service=managed,
            managed_hosts={"x99": ("uptime",)},
            bus=StimulusBus(capacity=16),
            journal=lambda stimulus: None,
            schedule=schedules(),
            accepted_stimulus_sink=accepted_stimulus_sink,
        )

    def test_builds_one_runtime_for_both_zones(self):
        runtime = self.build(WifiSource(), ManagedService())
        self.assertIsNotNone(runtime.run_once("wifi.presence"))
        self.assertIsNotNone(runtime.run_once("managed.x99"))

    def test_accepted_sink_is_forwarded_to_single_observation_runtime(self):
        received = []
        runtime = self.build(WifiSource(), ManagedService(), received.append)
        runtime.run_once("managed.x99")
        self.assertEqual(1, len(received))
        self.assertEqual("managed.x99", received[0].source)

    def test_managed_failure_does_not_block_wifi(self):
        wifi = WifiSource()
        runtime = self.build(wifi, ManagedService(RuntimeError("ssh down")))
        managed = runtime.run_once("managed.x99")
        wifi_result = runtime.run_once("wifi.presence")
        self.assertEqual(managed.kind, "source_error")
        self.assertEqual(wifi_result.payload["zone"], "WIFI_OBSERVED")
        self.assertEqual(wifi.calls, 1)

    def test_wifi_failure_does_not_block_managed(self):
        managed_service = ManagedService()
        runtime = self.build(WifiSource(RuntimeError("arp down")), managed_service)
        wifi = runtime.run_once("wifi.presence")
        managed = runtime.run_once("managed.x99")
        self.assertEqual(wifi.kind, "source_error")
        self.assertEqual(managed.payload["zone"], "MANAGED")
        self.assertEqual(managed_service.calls, [("x99", "uptime")])


if __name__ == "__main__":
    unittest.main()
