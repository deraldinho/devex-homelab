import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.memory_model import MemoryLayer, MemoryRecord
from infrastructure.pentium.atlas.memory_store import MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def test_round_trip_sqlite_sobrevive_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "atlas-memory.db"
            store = MemoryStore(path)
            registro = MemoryRecord(
                "m1", MemoryLayer.SEMANTIC, "2026-09-05T20:00:00+00:00",
                "core", "Core e membro do homelab", 0.9, 0.95, 3, "human",
                pinned=True, protected=True, dedupe_key="core-role",
            )
            store.save(registro)
            store.close()
            reopened = MemoryStore(path)
            restaurado = reopened.get("m1")
            reopened.close()
            self.assertEqual(registro, restaurado)

    def test_store_lista_e_mede_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.db")
            for idx in range(2):
                store.save(MemoryRecord(
                    f"m{idx}", MemoryLayer.EPISODIC, "2026-09-05T20:00:00+00:00",
                    "core", f"evento-{idx}", 0.5, 0.8, 1, "observation",
                ))
            self.assertEqual(2, store.count())
            self.assertGreater(store.size_bytes(), 0)
            self.assertEqual(2, len(store.list(limit=10)))
            store.close()


if __name__ == "__main__":
    unittest.main()


class MemoryStoreTransactionTests(unittest.TestCase):
    def test_consolidate_persiste_keeper_antes_de_remover_origens(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.db")
            a = MemoryRecord("a", MemoryLayer.EPISODIC, "2026-09-05T20:00:00+00:00", "core", "evento", 0.5, 0.8, 1, "observation", dedupe_key="k")
            b = MemoryRecord("b", MemoryLayer.EPISODIC, "2026-09-05T20:01:00+00:00", "core", "evento", 0.5, 0.8, 1, "observation", dedupe_key="k")
            store.save(a)
            store.save(b)
            merged = MemoryRecord("a", MemoryLayer.EPISODIC, a.created_at, "core", "evento", 0.5, 0.8, 2, "observation", dedupe_key="k")
            store.consolidate(merged, ("b",))
            self.assertEqual(1, store.count())
            self.assertEqual(2, store.get("a").frequency)
            self.assertIsNone(store.get("b"))
            store.close()


import sqlite3
from infrastructure.pentium.atlas.episodic_model import (
    EpisodeCategory, EpisodicEvidence, EpisodicSegment, SegmentStatus,
)
from infrastructure.pentium.atlas.memory_store import MemoryStoreError


def _segment(sid="seg-1", generation="gen-1"):
    return EpisodicSegment(
        sid, generation, EpisodeCategory.INCIDENT, "core", "incident:core",
        "2026-09-11T12:00:00+00:00", "2026-09-11T12:00:00+00:00",
    )


def _evidence(eid="e1", generation="gen-1"):
    return EpisodicEvidence(
        eid, "2026-09-11T12:00:01+00:00", "core.agent", "perception",
        "core indisponivel", 0.9, True, generation, "core-down", 0.8, 0.7, "core",
    )


class MemoryStoreV2Tests(unittest.TestCase):
    def _create_v1_db(self, path):
        db = sqlite3.connect(path)
        db.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.execute("INSERT INTO meta(key,value) VALUES('schema_version','1')")
        db.execute("""
            CREATE TABLE memories (
              memory_id TEXT PRIMARY KEY, layer TEXT NOT NULL, created_at TEXT NOT NULL,
              entity_id TEXT, content TEXT NOT NULL, importance REAL NOT NULL,
              confidence REAL NOT NULL, frequency INTEGER NOT NULL, origin TEXT NOT NULL,
              criticality REAL NOT NULL, pinned INTEGER NOT NULL, protected INTEGER NOT NULL,
              expires_at TEXT, dedupe_key TEXT
            )
        """)
        db.execute(
            "INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("legacy", "episodic", "2026-09-11T12:00:00+00:00", "core",
             "evento legado", 0.5, 0.8, 1, "observation", 0.0, 0, 0, None, None),
        )
        db.commit()
        db.close()

    def test_migra_v1_para_v2_sem_perder_memorias(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.db"
            self._create_v1_db(path)
            store = MemoryStore(path)
            self.assertEqual("2", store.schema_version())
            self.assertIsNotNone(store.get("legacy"))
            store.close()

    def test_segmento_e_evidencia_sobrevivem_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.db"
            store = MemoryStore(path)
            segment, evidence = _segment(), _evidence()
            store.save_segment(segment)
            store.append_evidence(segment.segment_id, evidence)
            store.close()
            reopened = MemoryStore(path)
            restored = reopened.get_segment(segment.segment_id)
            restored_evidence = reopened.list_evidence(segment.segment_id)
            reopened.close()
            self.assertEqual(segment.segment_id, restored.segment_id)
            self.assertEqual(1, restored.event_count)
            self.assertEqual(len(evidence.content_reduced.encode("utf-8")), restored.byte_count)
            self.assertEqual((evidence,), restored_evidence)
