import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from infrastructure.pentium.atlas.human_context import CognitiveContextUnavailable, HumanContextProvider
from infrastructure.pentium.atlas.tests.test_human_context_observation_bridge import HumanContextObservationBridgeTest


class HumanContextProviderTests(unittest.TestCase):
    def test_missing_health_is_degraded_but_keeps_real_observation_context(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            helper = HumanContextObservationBridgeTest()
            snapshot = helper.build_snapshot(root)
            provider = HumanContextProvider(
                root / "missing-health.json", snapshot, max_snapshot_age_s=180,
                expected_sha="abc", now=lambda: datetime.fromisoformat("2026-09-08T11:01:00+00:00"))
            ctx = provider()
            self.assertEqual("degraded", ctx["assessment"].state.value)
            self.assertEqual("x99", ctx["percepcao"].entidade_id)
            self.assertEqual("curioso", ctx["emocao"].principal)

    def test_missing_observation_snapshot_never_synthesizes_affect(self):
        with self.assertRaises(CognitiveContextUnavailable):
            HumanContextProvider(Path("missing-health"), Path("missing-snapshot"),
                                 max_snapshot_age_s=180)()


if __name__ == "__main__":
    unittest.main()
