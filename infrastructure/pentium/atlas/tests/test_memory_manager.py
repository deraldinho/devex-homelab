import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.memory_manager import MemoryManager, MemoryPolicy, MemoryPressure
from infrastructure.pentium.atlas.memory_model import MemoryLayer, MemoryRecord
from infrastructure.pentium.atlas.memory_store import MemoryStore


NOW = "2026-09-05T20:00:00+00:00"


def record(mid, *, content="evento", importance=0.2, confidence=0.5, frequency=1,
           criticality=0.0, protected=False, pinned=False, expires_at=None, dedupe_key=None):
    return MemoryRecord(
        mid, MemoryLayer.EPISODIC, NOW, "core", content,
        importance, confidence, frequency, "observation", criticality,
        pinned, protected, expires_at, dedupe_key,
    )


class MemoryManagerTests(unittest.TestCase):
    def test_classifica_pressao_nos_quatro_limites(self):
        policy = MemoryPolicy(max_records=100, max_bytes=100000)
        self.assertEqual(MemoryPressure.NORMAL, policy.classify(0.69))
        self.assertEqual(MemoryPressure.CLEANUP, policy.classify(0.70))
        self.assertEqual(MemoryPressure.CONSOLIDATE, policy.classify(0.85))
        self.assertEqual(MemoryPressure.EVICT, policy.classify(0.95))
        self.assertEqual(MemoryPressure.FULL, policy.classify(1.00))

    def test_cleanup_remove_expirada_mas_preserva_protegida(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.db")
            policy = MemoryPolicy(max_records=3, max_bytes=100000)
            manager = MemoryManager(store, policy)
            store.save(record("old", expires_at="2026-09-05T19:00:00+00:00"))
            store.save(record("safe", protected=True, expires_at="2026-09-05T19:00:00+00:00"))
            store.save(record("new"))
            result = manager.maintain(NOW)
            self.assertIn("old", result.removed_ids)
            self.assertIsNotNone(store.get("safe"))
            store.close()

    def test_dedupe_incrementa_frequencia_sem_criar_novo_registro(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.db")
            manager = MemoryManager(store, MemoryPolicy(max_records=10, max_bytes=100000))
            self.assertTrue(manager.remember(record("a", dedupe_key="core-reboot"), NOW))
            self.assertTrue(manager.remember(record("b", dedupe_key="core-reboot"), NOW))
            self.assertEqual(1, store.count())
            self.assertEqual(2, store.get("a").frequency)
            store.close()

    def test_eviction_remove_menor_score_e_preserva_pinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.db")
            manager = MemoryManager(store, MemoryPolicy(max_records=4, max_bytes=100000))
            store.save(record("low", importance=0.1, confidence=0.2))
            store.save(record("mid", importance=0.5, confidence=0.5))
            store.save(record("high", importance=0.9, confidence=0.9, criticality=0.8))
            store.save(record("pin", importance=0.0, confidence=0.0, pinned=True))
            result = manager.maintain(NOW)
            self.assertIn("low", result.removed_ids)
            self.assertIsNotNone(store.get("pin"))
            self.assertIsNotNone(store.get("high"))
            store.close()

    def test_full_rejeita_descartavel_mas_aceita_protegida(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.db")
            manager = MemoryManager(store, MemoryPolicy(max_records=1, max_bytes=100000))
            store.save(record("existing"))
            self.assertFalse(manager.remember(record("drop"), NOW))
            self.assertTrue(manager.remember(record("protected", protected=True), NOW))
            self.assertIsNotNone(store.get("protected"))
            store.close()


if __name__ == "__main__":
    unittest.main()
