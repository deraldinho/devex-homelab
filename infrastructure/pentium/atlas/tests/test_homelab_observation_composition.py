import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from infrastructure.pentium.atlas.dual_zone_runtime import build_dual_zone_runtime
from infrastructure.pentium.atlas.local_health import collect_pentium_self
from infrastructure.pentium.atlas.observation_runtime import SourceSchedule
from infrastructure.pentium.atlas.stimulus_bus import StimulusBus
from infrastructure.pentium.atlas.stimulus_model import StimulusSeverity
from infrastructure.pentium.atlas.stimulus_sources import PentiumSelfSource, SourceSnapshot


class WifiSource:
    name = "wifi.presence"
    required = False
    def poll(self):
        return SourceSnapshot(self.name, "healthy", StimulusSeverity.INFO, {"zone": "WIFI_OBSERVED"})


class ManagedService:
    def __init__(self): self.calls = []
    def read(self, host_id, operation):
        self.calls.append((host_id, operation.value))
        return {"status": "healthy", "host": host_id, "operation": operation.value}


def schedule():
    names = ("pentium.self", "wifi.presence", "managed.core", "managed.x99")
    return {name: SourceSchedule(60, 1, 120, 0) for name in names}


class HomeLabObservationCompositionTests(unittest.TestCase):
    def test_local_health_exposes_affective_health_signal(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            meminfo=root/"meminfo"
            meminfo.write_text("MemAvailable: 1048576 kB\n",encoding="utf-8")
            healthy=collect_pentium_self(meminfo_path=meminfo,disk_path=root)
            degraded=collect_pentium_self(meminfo_path=root/"missing",disk_path=root)
        self.assertTrue(healthy["self_healthy"])
        self.assertFalse(degraded["self_healthy"])

    def test_pentium_source_preserves_affective_health_signal(self):
        source=PentiumSelfSource(lambda: {
            "status":"degraded","self_healthy":False,"checks":{"memory":{"ok":False}},"metrics":{}
        })
        snapshot=source.poll()
        self.assertIn("self_healthy",snapshot.payload)
        self.assertFalse(snapshot.payload["self_healthy"])

    def test_runtime_contains_local_core_x99_and_wifi_sources(self):
        local = PentiumSelfSource(lambda: {"status": "healthy", "checks": {}, "metrics": {}})
        managed = ManagedService()
        runtime = build_dual_zone_runtime(
            wifi_source=WifiSource(),
            managed_read_service=managed,
            managed_hosts={"core": ("uptime",), "x99": ("uptime",)},
            local_sources=(local,),
            bus=StimulusBus(capacity=16),
            journal=lambda stimulus: None,
            schedule=schedule(),
        )
        self.assertEqual("pentium.self", runtime.run_once("pentium.self").source)
        self.assertEqual("managed.core", runtime.run_once("managed.core").source)
        self.assertEqual("managed.x99", runtime.run_once("managed.x99").source)
        self.assertEqual("wifi.presence", runtime.run_once("wifi.presence").source)
        self.assertEqual([("core", "uptime"), ("x99", "uptime")], managed.calls)


if __name__ == "__main__":
    unittest.main()
