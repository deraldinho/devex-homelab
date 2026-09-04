import dataclasses
import json
import unittest

from infrastructure.pentium.atlas.stimulus_model import (
    Stimulus,
    StimulusSeverity,
    compute_novelty,
    stable_fingerprint,
)


class StimulusModelTests(unittest.TestCase):
    def test_severity_contract_is_stable(self):
        self.assertEqual(
            [item.value for item in StimulusSeverity],
            ["info", "notice", "warning", "critical"],
        )

    def test_stimulus_is_frozen_and_json_serializable(self):
        stimulus = Stimulus(
            stimulus_id="stim-1",
            source="core",
            kind="status_changed",
            severity=StimulusSeverity.WARNING,
            timestamp="2026-09-04T01:00:00+00:00",
            payload={"status": "degraded"},
            novelty=0.75,
            correlation_id="corr-1",
            previous_fingerprint="aaa",
            current_fingerprint="bbb",
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            stimulus.kind = "other"
        encoded = json.dumps(stimulus.to_dict(), sort_keys=True)
        self.assertIn('"severity": "warning"', encoded)
        self.assertIn('"status": "degraded"', encoded)

    def test_fingerprint_is_order_independent(self):
        left = {"status": "healthy", "metrics": {"cpu": 12, "ram": 40}}
        right = {"metrics": {"ram": 40, "cpu": 12}, "status": "healthy"}
        self.assertEqual(stable_fingerprint(left), stable_fingerprint(right))
        self.assertNotEqual(
            stable_fingerprint(left),
            stable_fingerprint({"status": "degraded", "metrics": {"cpu": 12, "ram": 40}}),
        )

    def test_novelty_decays_deterministically_to_floor(self):
        self.assertEqual(compute_novelty(0), 1.0)
        self.assertEqual(compute_novelty(1), 0.5)
        self.assertEqual(compute_novelty(99), 0.1)

    def test_novelty_rejects_negative_seen_count(self):
        with self.assertRaises(ValueError):
            compute_novelty(-1)


if __name__ == "__main__":
    unittest.main()
