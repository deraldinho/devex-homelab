import unittest

from infrastructure.pentium.atlas.i1_certification import certify_dual_zone


class FakeStimulus:
    def __init__(self, *, kind="baseline_observed", zone=None):
        self.kind = kind
        self.payload = {}
        if zone is not None:
            self.payload["zone"] = zone


class FakeRuntime:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def run_once(self, name):
        self.calls.append(name)
        return self.mapping[name]


class I1CertificationTests(unittest.TestCase):
    def test_pass_requires_both_zones_and_control_default_deny(self):
        runtime = FakeRuntime({
            "wifi.presence": FakeStimulus(zone="WIFI_OBSERVED"),
            "managed.x99": FakeStimulus(zone="MANAGED"),
        })
        result = certify_dual_zone(runtime, managed_sources=("managed.x99",), control_default_deny=lambda: True)
        self.assertTrue(result.passed)
        self.assertFalse(result.physical_certified)
        self.assertEqual(result.marker, "ATLAS_I1_OBSERVATION_INTEGRATION_PASS")

    def test_source_error_blocks_certification_but_not_physical_flag(self):
        runtime = FakeRuntime({
            "wifi.presence": FakeStimulus(zone="WIFI_OBSERVED"),
            "managed.x99": FakeStimulus(kind="source_error"),
        })
        result = certify_dual_zone(runtime, managed_sources=("managed.x99",), control_default_deny=lambda: True)
        self.assertFalse(result.passed)
        self.assertFalse(result.physical_certified)
        self.assertIsNone(result.marker)

    def test_control_guard_failure_blocks_certification(self):
        runtime = FakeRuntime({
            "wifi.presence": FakeStimulus(zone="WIFI_OBSERVED"),
            "managed.x99": FakeStimulus(zone="MANAGED"),
        })
        result = certify_dual_zone(runtime, managed_sources=("managed.x99",), control_default_deny=lambda: False)
        self.assertFalse(result.passed)


if __name__ == "__main__":
    unittest.main()
