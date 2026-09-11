import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from infrastructure.pentium.atlas.config_memory import MemoryConfig
from infrastructure.pentium.atlas.episodic_ingestion import EpisodicMemorySink
from infrastructure.pentium.atlas.episodic_model import SegmentStatus
from infrastructure.pentium.atlas.memory_manager import MemoryManager, MemoryPolicy
from infrastructure.pentium.atlas.memory_store import MemoryStore
from infrastructure.pentium.atlas.modelo_incidente import EstadoRecuperacaoIncidente, IncidenteTecnico
from infrastructure.pentium.atlas.modelo_percepcao import EstadoObservacao, EstadoPercepcao
from infrastructure.pentium.atlas.pipeline_percepcao_correlacao import ResultadoPipelinePercepcaoCorrelacao


NOW = "2026-09-11T12:30:00+00:00"
LATER = "2026-09-11T12:31:00+00:00"


def cfg():
    return MemoryConfig(
        1, 100, 100000, .70, .85, .95, 6, 2048,
        episodic_max_events=8, episodic_max_bytes=2048,
        episodic_max_open_segments=8, episodic_max_pending_bytes=8192,
        episodic_idle_timeout_s=30,
    )


def perception(at=NOW):
    return EstadoPercepcao(
        "core", EstadoObservacao.INACESSIVEL, .9, at,
        ("core.agent",), (), False, at,
    )

def incident(state=EstadoRecuperacaoIncidente.ABERTO, *, at=NOW):
    return IncidenteTecnico(
        "inc-1", "core", "indisponibilidade_correlacionada", "critical",
        NOW, "core", .9, ("core",), 1,
        estado_recuperacao=state,
        recuperado_em=at if state is EstadoRecuperacaoIncidente.RECUPERADO else None,
    )


def result(inc, *, accepted=True, at=NOW):
    return ResultadoPipelinePercepcaoCorrelacao(accepted, perception(at), (inc,))


class EpisodicIngestionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "memory.db"
        self.store = MemoryStore(self.path)
        self.manager = MemoryManager(self.store, MemoryPolicy(100, 100000))
        ids = iter(("seg-1", "seg-2", "seg-3", "seg-4"))
        self.sink = EpisodicMemorySink(
            self.store, cfg(), self.manager, generation_id="gen-1",
            id_factory=ids.__next__,
        )

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()
    def test_incident_open_then_recovery_creates_one_memory(self):
        self.sink(result(incident()))
        self.assertEqual(0, self.store.count())
        self.sink(result(incident(EstadoRecuperacaoIncidente.RECUPERADO, at=LATER), at=LATER))
        self.assertEqual(1, self.store.count())
        self.assertEqual(SegmentStatus.CONSOLIDATED, self.store.get_segment("seg-1").status)

    def test_restart_recovery_consolidates_old_generation_once(self):
        self.sink(result(incident()))
        ids = iter(("seg-10", "seg-11"))
        new_sink = EpisodicMemorySink(
            self.store, cfg(), self.manager, generation_id="gen-2",
            id_factory=ids.__next__,
        )
        new_sink.recover(LATER)
        new_sink.recover(LATER)
        self.assertEqual(1, self.store.count())
        self.assertEqual(SegmentStatus.CONSOLIDATED, self.store.get_segment("seg-1").status)

    def test_rejected_pipeline_result_is_ignored(self):
        self.sink(result(incident(), accepted=False))
        self.assertEqual(0, len(self.store.list_open_segments()))
        self.assertEqual(0, self.store.count())

    def test_flush_idle_consolidates_closed_segment(self):
        self.sink(result(incident()))
        self.sink.flush_idle("2026-09-11T12:31:00+00:00")
        self.assertEqual(1, self.store.count())
        self.assertGreaterEqual(self.sink.metrics.get("consolidation_success_total"), 1)


if __name__ == "__main__":
    unittest.main()
