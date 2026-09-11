import sqlite3
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.episodic_consolidator import EpisodicConsolidator
from infrastructure.pentium.atlas.episodic_model import (
    ClosureReason, EpisodeCategory, EpisodicEvidence, EpisodicSegment, SegmentStatus,
)
from infrastructure.pentium.atlas.memory_manager import MemoryManager, MemoryPolicy
from infrastructure.pentium.atlas.memory_store import MemoryStore


NOW = "2026-09-11T12:10:00+00:00"


def evidence(eid="e1", generation="gen-1", *, verified=True, reliability=.9, content="core indisponivel"):
    return EpisodicEvidence(
        eid, NOW, "core.agent", "incident", content, reliability, verified,
        generation, "incident:core", .8, .7, "core",
    )


def seed_closed(store, *, segment_id="seg-1", generation="gen-1", items=None):
    items = tuple(items or (evidence(generation=generation),))
    segment = EpisodicSegment(
        segment_id, generation, EpisodeCategory.INCIDENT, "core", "incident:core",
        NOW, NOW,
    )
    store.save_segment(segment)
    for item in items:
        store.append_evidence(segment_id, item)
    store.close_segment(segment_id, ClosureReason.TERMINAL_EVENT, NOW)


class EpisodicConsolidatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "memory.db"
        self.store = MemoryStore(self.path)
        seed_closed(self.store)
        self.manager = MemoryManager(self.store, MemoryPolicy(100, 100000))
        self.consolidator = EpisodicConsolidator(self.store, self.manager)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_retry_same_segment_is_exactly_once(self):
        self.assertTrue(self.consolidator.consolidate("seg-1", NOW))
        before = self.store.count()
        frequency = self.store.list(limit=10)[0].frequency
        self.assertFalse(self.consolidator.consolidate("seg-1", NOW))
        self.assertEqual(before, self.store.count())
        self.assertEqual(frequency, self.store.list(limit=10)[0].frequency)
        self.assertEqual(1, self.store.get_provenance("seg-1").evidence_count)
    def test_mixed_generation_segment_fails_closed(self):
        raw = sqlite3.connect(self.path)
        try:
            raw.execute("UPDATE episodic_evidence SET generation_id='gen-2' WHERE event_id='e1'")
            raw.commit()
        finally:
            raw.close()
        with self.assertRaises(ValueError):
            self.consolidator.consolidate("seg-1", NOW)
        self.assertEqual(SegmentStatus.CLOSED, self.store.get_segment("seg-1").status)
        self.assertEqual(0, self.store.count())

    def test_unverified_evidence_does_not_raise_confidence(self):
        self.store.close()
        self.path.unlink(missing_ok=True)
        self.store = MemoryStore(self.path)
        seed_closed(self.store, items=(
            evidence("e1", verified=True, reliability=.4),
            evidence("e2", verified=False, reliability=1.0, content="nao verificado"),
        ))
        self.manager = MemoryManager(self.store, MemoryPolicy(100, 100000))
        self.consolidator = EpisodicConsolidator(self.store, self.manager)
        self.assertTrue(self.consolidator.consolidate("seg-1", NOW))
        self.assertAlmostEqual(.4, self.store.list(limit=1)[0].confidence, places=9)


if __name__ == "__main__":
    unittest.main()
