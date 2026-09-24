"""Testes do Hypothesis Engine."""
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.autonomy.hypothesis_engine import (
    Hypothesis,
    HypothesisEngine,
    HypothesisStatus,
)


class HypothesisModelTests(unittest.TestCase):
    def test_valida_campos(self):
        with self.assertRaises(ValueError):
            Hypothesis("", "title", "desc")
        with self.assertRaises(ValueError):
            Hypothesis("h1", "", "desc")
        with self.assertRaises(ValueError):
            Hypothesis("h1", "title", "desc", confidence=1.5)

    def test_evidence_balance(self):
        h = Hypothesis("h1", "test", "desc")
        h.evidence_for = ["a", "b"]
        h.evidence_against = ["c"]
        self.assertAlmostEqual(1 / 3, h.evidence_balance, places=2)

    def test_terminal_states(self):
        h = Hypothesis("h1", "test", "desc", status=HypothesisStatus.CONFIRMED)
        self.assertTrue(h.is_terminal)
        h2 = Hypothesis("h2", "test", "desc", status=HypothesisStatus.PROPOSED)
        self.assertFalse(h2.is_terminal)


class HypothesisEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "hypotheses.json"
        self.engine = HypothesisEngine(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_propose_and_get(self):
        h = self.engine.propose("h1", "Disco Core crescendo", "Disco /data crescendo 0.3%/h")
        self.assertEqual(HypothesisStatus.PROPOSED, h.status)
        got = self.engine.get("h1")
        self.assertIsNotNone(got)
        self.assertEqual("Disco Core crescendo", got.title)

    def test_add_evidence_transitions_to_investigating(self):
        self.engine.propose("h1", "Test", "desc")
        h = self.engine.add_evidence("h1", "Observação: disco 87%", supports=True)
        self.assertEqual(HypothesisStatus.INVESTIGATING, h.status)

    def test_evidence_updates_confidence(self):
        self.engine.propose("h1", "Test", "desc")
        for i in range(3):
            self.engine.add_evidence("h1", f"Evidência {i}", supports=True)
        h = self.engine.get("h1")
        self.assertGreater(h.confidence, 0.5)

    def test_resolve_hypothesis(self):
        self.engine.propose("h1", "Test", "desc")
        h = self.engine.resolve("h1", HypothesisStatus.CONFIRMED, "Disco confirmado cheio")
        self.assertEqual(HypothesisStatus.CONFIRMED, h.status)
        self.assertTrue(h.is_terminal)
        self.assertTrue(h.resolved_at)

    def test_cannot_resolve_terminal(self):
        self.engine.propose("h1", "Test", "desc")
        self.engine.resolve("h1", HypothesisStatus.CONFIRMED)
        result = self.engine.resolve("h1", HypothesisStatus.REFUTED)
        self.assertIsNone(result)

    def test_list_active(self):
        self.engine.propose("h1", "Active", "desc")
        self.engine.propose("h2", "Also active", "desc")
        self.engine.propose("h3", "Will resolve", "desc")
        self.engine.resolve("h3", HypothesisStatus.REFUTED)
        active = self.engine.list_active()
        self.assertEqual(2, len(active))

    def test_max_active_limit(self):
        for i in range(10):
            self.engine.propose(f"h{i}", f"Hypothesis {i}", "desc")
        with self.assertRaises(OverflowError):
            self.engine.propose("h_overflow", "Too many", "desc")

    def test_persistence(self):
        self.engine.propose("h1", "Persistent", "desc", source="trend")
        self.engine.add_evidence("h1", "Evidence 1", supports=True)
        engine2 = HypothesisEngine(self.path)
        h = engine2.get("h1")
        self.assertIsNotNone(h)
        self.assertEqual("Persistent", h.title)
        self.assertEqual(1, len(h.evidence_for))

    def test_expire_stale(self):
        h = self.engine.propose("h1", "Old", "desc")
        h.updated_at = "2020-01-01T00:00:00+00:00"
        self.engine._save()
        expired = self.engine.expire_stale(max_age_hours=1.0)
        self.assertIn("h1", expired)
        self.assertEqual(HypothesisStatus.EXPIRED, self.engine.get("h1").status)


if __name__ == "__main__":
    unittest.main()
