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
