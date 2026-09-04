import dataclasses
import json
import unittest

from infrastructure.pentium.atlas.state_model import (
    GlobalAssessment,
    ReactionDecision,
    Signal,
    TechnicalState,
)


class StateModelTests(unittest.TestCase):
    def test_technical_state_enum_is_complete(self):
        self.assertEqual(
            [state.value for state in TechnicalState],
            ["healthy", "active", "busy", "degraded", "stressed", "critical", "recovered"],
        )

    def test_signal_clamps_intensity(self):
        low = Signal("core", TechnicalState.HEALTHY, -3)
        high = Signal("core", TechnicalState.STRESSED, 99)
        self.assertEqual(low.intensity, 0)
        self.assertEqual(high.intensity, 4)

    def test_structures_are_frozen_and_json_serializable(self):
        signal = Signal("core", TechnicalState.BUSY, 2, reason="core.cpu.high")
        assessment = GlobalAssessment(
            previous_state=TechnicalState.HEALTHY,
            state=TechnicalState.BUSY,
            intensity=2,
            reasons=("core:core.cpu.high",),
        )
        decision = ReactionDecision("busy", "busy.tech.01")

        with self.assertRaises(dataclasses.FrozenInstanceError):
            signal.intensity = 3

        payload = {
            "signal": signal.to_dict(),
            "assessment": assessment.to_dict(),
            "decision": decision.to_dict(),
        }
        encoded = json.dumps(payload, sort_keys=True)
        self.assertIn('"state": "busy"', encoded)
        self.assertIn('"reaction_id": "busy.tech.01"', encoded)


if __name__ == "__main__":
    unittest.main()
