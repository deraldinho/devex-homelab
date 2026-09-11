import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.config_memory import MemoryConfig
from infrastructure.pentium.atlas.episodic_buffer import EpisodicBuffer
from infrastructure.pentium.atlas.episodic_model import (
    ClosureReason, EpisodeCategory, EpisodicEvidence, SegmentStatus,
)
from infrastructure.pentium.atlas.memory_store import MemoryStore


NOW = "2026-09-11T12:00:00+00:00"


def cfg(**overrides):
    values = dict(
        schema_version=1, max_records=100, max_bytes=100000,
        cleanup_ratio=.70, consolidate_ratio=.85, evict_ratio=.95,
        retriever_max_items=6, retriever_max_bytes=2048,
        episodic_max_events=3, episodic_max_bytes=64,
        episodic_max_open_segments=2, episodic_max_pending_bytes=96,
        episodic_idle_timeout_s=10,
    )
    values.update(overrides)
    return MemoryConfig(**values)


def evidence(eid, generation, content="core down", at=NOW):
    return EpisodicEvidence(
        eid, at, "core.agent", "perception", content, .9, True,
        generation, "core-down", .8, .7, "core",
    )


class EpisodicBufferTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "memory.db")
        ids = iter(("seg-1", "seg-2", "seg-3", "seg-4"))
        self.buffer = EpisodicBuffer(self.store, cfg(), id_factory=ids.__next__)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_generation_mismatch_fecha_antigo_e_abre_novo(self):
        first = self.buffer.ingest(evidence("e1", "gen-1"), EpisodeCategory.INCIDENT, "incident:core")
        second = self.buffer.ingest(evidence("e2", "gen-2"), EpisodeCategory.INCIDENT, "incident:core")
        old = self.store.get_segment(first.segment_id)
        self.assertEqual(SegmentStatus.CLOSED, old.status)
        self.assertEqual(ClosureReason.GENERATION_FENCE, old.closure_reason)
        self.assertNotEqual(first.segment_id, second.segment_id)

    def test_pending_bytes_nunca_ultrapassa_bound_global(self):
        self.buffer.ingest(evidence("e1", "gen-1", "x" * 60), EpisodeCategory.GENERIC, "g:1")
        with self.assertRaises(OverflowError):
            self.buffer.ingest(evidence("e2", "gen-1", "y" * 40), EpisodeCategory.GENERIC, "g:2")
        self.assertLessEqual(self.buffer.pending_bytes(), 96)

    def test_terminal_event_fecha_segmento(self):
        result = self.buffer.ingest(
            evidence("e1", "gen-1"), EpisodeCategory.INCIDENT,
            "incident:core", terminal=True,
        )
        restored = self.store.get_segment(result.segment_id)
        self.assertEqual(SegmentStatus.CLOSED, restored.status)
        self.assertEqual(ClosureReason.TERMINAL_EVENT, restored.closure_reason)

    def test_idle_timeout_fecha_segmento(self):
        self.buffer.ingest(evidence("e1", "gen-1"), EpisodeCategory.GENERIC, "g:1")
        closed = self.buffer.close_idle("2026-09-11T12:00:11+00:00")
        self.assertEqual(("seg-1",), closed)
        self.assertEqual(ClosureReason.IDLE_TIMEOUT, self.store.get_segment("seg-1").closure_reason)

    def test_restart_recovery_fecha_somente_geracao_anterior(self):
        self.buffer.ingest(evidence("e1", "gen-old"), EpisodeCategory.GENERIC, "g:1")
        recovered = self.buffer.recover_previous_generation("gen-new", "2026-09-11T12:01:00+00:00")
        self.assertEqual(("seg-1",), recovered)
        restored = self.store.get_segment("seg-1")
        self.assertEqual(SegmentStatus.CLOSED, restored.status)
        self.assertEqual(ClosureReason.RESTART_RECOVERY, restored.closure_reason)


if __name__ == "__main__":
    unittest.main()
