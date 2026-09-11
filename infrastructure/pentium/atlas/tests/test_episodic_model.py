import unittest

from infrastructure.pentium.atlas.episodic_model import (
    ClosureReason,
    EpisodeCategory,
    EpisodicEvidence,
    EpisodicSegment,
    MemoryProvenance,
    SegmentStatus,
)


NOW = "2026-09-11T12:00:00+00:00"


class EpisodicModelTests(unittest.TestCase):
    def test_evidence_normaliza_timestamp_e_valida_bounds(self):
        item = EpisodicEvidence(
            "e1", NOW, "core.agent", "perception", "core indisponivel",
            0.9, True, "gen-1", "core-down", 0.8, 0.7, "core",
        )
        self.assertEqual("2026-09-11T12:00:00+00:00", item.occurred_at)
        self.assertEqual(0.9, item.reliability)
        with self.assertRaises(ValueError):
            EpisodicEvidence("e2", NOW, "s", "k", "x", 1.1, True, "gen-1")

    def test_segmento_exige_closure_reason_quando_fechado(self):
        with self.assertRaises(ValueError):
            EpisodicSegment(
                "seg-1", "gen-1", EpisodeCategory.INCIDENT, "core", "incident:1",
                NOW, NOW, SegmentStatus.CLOSED, None, 1, 10,
            )
        closed = EpisodicSegment(
            "seg-1", "gen-1", EpisodeCategory.INCIDENT, "core", "incident:1",
            NOW, NOW, SegmentStatus.CLOSED, ClosureReason.TERMINAL_EVENT, 1, 10,
        )
        self.assertEqual(SegmentStatus.CLOSED, closed.status)

    def test_provenance_deduplica_fontes_e_valida_contagem(self):
        item = MemoryProvenance(
            "seg-1", "m1", "gen-1", ("core.agent", "core.agent", "core.ping"),
            NOW, NOW, 2,
        )
        self.assertEqual(("core.agent", "core.ping"), item.sources)
        with self.assertRaises(ValueError):
            MemoryProvenance("seg-1", "m1", "gen-1", (), NOW, NOW, 0)


if __name__ == "__main__":
    unittest.main()
