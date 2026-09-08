import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from infrastructure.pentium.atlas.cognitive_observation_projection import CognitiveObservationPublisher
from infrastructure.pentium.atlas.human_context import CognitiveContextUnavailable, HumanContextProvider
from infrastructure.pentium.atlas.tests.test_cognitive_observation_projection import CognitiveObservationProjectionTest, NOW


class HumanContextObservationBridgeTest(unittest.TestCase):
    def build_snapshot(self, root: Path, *, expected_sha="abc"):
        helper = CognitiveObservationProjectionTest()
        path = root / "cognitive-observation-context.json"
        publisher = CognitiveObservationPublisher(path, helper.policy(), expected_sha=expected_sha)
        publisher.publish(helper.stimulus(), helper.result_a3(), helper.impact(), helper.focus_result(), (helper.stimulus(),))
        return path

    def write_health(self, root: Path, status="healthy"):
        path = root / "health.json"
        path.write_text(json.dumps({"status": status}), encoding="utf-8")
        return path

    def provider(self, health, snapshot, *, now="2026-09-08T11:01:00+00:00", expected_sha="abc"):
        return HumanContextProvider(
            health, snapshot, max_snapshot_age_s=180,
            expected_sha=expected_sha,
            now=lambda: datetime.fromisoformat(now),
        )

    def test_provider_reconstructs_real_a1_a3_a4_and_only_health_assessment(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            snapshot = self.build_snapshot(root)
            health = self.write_health(root, "healthy")
            context = self.provider(health, snapshot)()
            self.assertEqual("healthy", context["assessment"].state.value)
            self.assertEqual("x99", context["percepcao"].entidade_id)
            self.assertEqual("inc-1", context["incidente"].incidente_id)
            self.assertAlmostEqual(0.8, context["estado_afetivo"].curiosidade)
            self.assertEqual("curioso", context["emocao"].principal)
            self.assertEqual("inc-1", context["foco"].principal.assunto_id)
            self.assertEqual(("core",), context["dependencias_afetadas"])
            self.assertEqual("s1", context["mudancas_recentes"][0].stimulus_id)

    def test_degraded_health_changes_only_assessment(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            snapshot = self.build_snapshot(root)
            health = self.write_health(root, "degraded")
            context = self.provider(health, snapshot)()
            self.assertEqual("degraded", context["assessment"].state.value)
            self.assertEqual("x99", context["percepcao"].entidade_id)
            self.assertEqual("curioso", context["emocao"].principal)

    def test_missing_corrupt_stale_and_sha_mismatch_raise_unavailable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            health = self.write_health(root)
            missing = root / "missing.json"
            with self.assertRaises(CognitiveContextUnavailable):
                self.provider(health, missing)()

            corrupt = root / "corrupt.json"
            corrupt.write_text("{not-json", encoding="utf-8")
            with self.assertRaises(CognitiveContextUnavailable):
                self.provider(health, corrupt)()

            stale = self.build_snapshot(root)
            with self.assertRaises(CognitiveContextUnavailable):
                self.provider(health, stale, now="2026-09-08T11:10:00+00:00")()

            mismatch = self.build_snapshot(root, expected_sha="def")
            with self.assertRaises(CognitiveContextUnavailable):
                self.provider(health, mismatch, expected_sha="abc")()


if __name__ == "__main__":
    unittest.main()
