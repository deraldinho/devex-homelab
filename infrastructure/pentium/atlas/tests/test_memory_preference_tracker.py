"""Testes do Memory Preference Tracker."""
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.memory_preference_tracker import (
    PreferenceSignal,
    PreferenceTracker,
)


NOW = "2026-09-22T14:30:00-03:00"
LATER = "2026-09-22T15:00:00-03:00"


class PreferenceSignalTests(unittest.TestCase):
    def test_signal_valida_campos(self):
        with self.assertRaises(ValueError):
            PreferenceSignal("", "key")
        with self.assertRaises(ValueError):
            PreferenceSignal("topic", "")


class PreferenceTrackerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "prefs.json"
        self.tracker = PreferenceTracker(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_record_and_retrieve_topic(self):
        self.tracker.record(PreferenceSignal("topic", "l2jtoren", 1.0, NOW))
        self.tracker.record(PreferenceSignal("topic", "l2jtoren", 1.0, LATER))
        self.tracker.record(PreferenceSignal("topic", "backup", 1.0, NOW))
        tops = self.tracker.top_topics(3)
        self.assertEqual("l2jtoren", tops[0][0])
        self.assertAlmostEqual(2.0, tops[0][1])

    def test_record_schedule(self):
        self.tracker.record(PreferenceSignal("schedule", "active_hour:14", 1.0, NOW))
        self.tracker.record(PreferenceSignal("schedule", "active_hour:14", 1.0, LATER))
        self.tracker.record(PreferenceSignal("schedule", "active_hour:22", 1.0, NOW))
        hours = self.tracker.active_hours()
        self.assertEqual(14, hours[0])

    def test_record_style(self):
        self.tracker.record(PreferenceSignal("style", "architect", 3.0, NOW))
        self.tracker.record(PreferenceSignal("style", "direct", 1.0, NOW))
        self.assertEqual("architect", self.tracker.preferred_style())

    def test_decay_reduces_weights(self):
        self.tracker.record(PreferenceSignal("topic", "l2jtoren", 1.0, NOW))
        before = self.tracker.profile.topics["l2jtoren"]
        self.tracker.decay()
        after = self.tracker.profile.topics["l2jtoren"]
        self.assertLess(after, before)

    def test_decay_removes_negligible(self):
        self.tracker.record(PreferenceSignal("topic", "tiny", 0.005, NOW))
        self.tracker.decay()
        self.assertNotIn("tiny", self.tracker.profile.topics)

    def test_persistence_across_restart(self):
        self.tracker.record(PreferenceSignal("topic", "l2jtoren", 5.0, NOW))
        self.tracker.record(PreferenceSignal("style", "partner", 2.0, NOW))
        # Simular restart
        tracker2 = PreferenceTracker(self.path)
        self.assertAlmostEqual(5.0, tracker2.profile.topics["l2jtoren"])
        self.assertEqual("partner", tracker2.preferred_style())

    def test_derive_signals_from_message(self):
        signals = self.tracker.derive_signals_from_message(
            "Vamos discutir a arquitetura e o trade-off do container-first no homelab",
            timestamp=NOW,
            topics=("container-first", "arquitetura"),
        )
        cats = {s.category for s in signals}
        self.assertIn("schedule", cats)
        self.assertIn("topic", cats)
        self.assertIn("style", cats)
        style_signals = [s for s in signals if s.category == "style"]
        self.assertEqual("architect", style_signals[0].key)

    def test_derive_direct_style(self):
        signals = self.tracker.derive_signals_from_message(
            "Status do Core?",
            timestamp=NOW,
        )
        style_signals = [s for s in signals if s.category == "style"]
        self.assertEqual("direct", style_signals[0].key)

    def test_total_interactions_count(self):
        for i in range(5):
            self.tracker.record(PreferenceSignal("topic", f"t{i}", 1.0, NOW))
        self.assertEqual(5, self.tracker.profile.total_interactions)

    def test_bounded_entries(self):
        for i in range(60):
            self.tracker.record(PreferenceSignal("topic", f"topic_{i}", 1.0, NOW))
        self.tracker.decay()
        self.assertLessEqual(len(self.tracker.profile.topics), 50)


if __name__ == "__main__":
    unittest.main()
