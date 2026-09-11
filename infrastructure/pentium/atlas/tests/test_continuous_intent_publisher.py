import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.continuous_intent import ContinuousIntent, IntentState, IntentType
from infrastructure.pentium.atlas.continuous_intent_publisher import ContinuousIntentPublisher


class ContinuousIntentPublisherTests(unittest.TestCase):
    def test_atomic_snapshot_contains_bounded_operational_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"continuous-intent.json"
            intent=ContinuousIntent(
                "i1", IntentType.ACOMPANHAR_RECUPERACAO, IntentState.ATIVA,
                "core", "core", "degraded", .8,
                "2026-09-11T12:00:00+00:00", "2026-09-11T12:00:00+00:00",
                "2026-09-11T12:05:00+00:00",
            )
            ContinuousIntentPublisher(path).publish(
                intent, communication_mode="silent_tracking", material_fingerprint="x"*400,
            )
            payload=json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(1,payload["schema_version"])
            self.assertEqual("ATIVA",payload["intent"]["estado"])
            self.assertEqual("silent_tracking",payload["communication_mode"])
            self.assertLessEqual(len(payload["material_fingerprint"]),256)
            self.assertFalse(path.with_name(path.name+".tmp").exists())

    def test_none_intent_is_valid_debug_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"continuous-intent.json"
            ContinuousIntentPublisher(path).publish(None,communication_mode="normal",material_fingerprint="")
            self.assertIsNone(json.loads(path.read_text(encoding="utf-8"))["intent"])


if __name__ == "__main__": unittest.main()
