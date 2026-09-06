import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.memory_model import MemoryLayer, MemoryRecord
from infrastructure.pentium.atlas.memory_retriever import MemoryRetriever
from infrastructure.pentium.atlas.memory_store import MemoryStore


class MemoryRetrieverTests(unittest.TestCase):
    def test_prioriza_entidade_e_limita_itens_e_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.db")
            for idx in range(5):
                store.save(MemoryRecord(
                    f"c{idx}", MemoryLayer.EPISODIC, f"2026-09-05T20:00:0{idx}+00:00",
                    "core", f"Core incidente rede {idx}", 0.7, 0.8, 1, "observation",
                ))
            store.save(MemoryRecord(
                "x", MemoryLayer.SEMANTIC, "2026-09-05T20:00:09+00:00",
                "x99", "x99 runner", 1.0, 1.0, 10, "human",
            ))
            result = MemoryRetriever(store, max_items=3, max_bytes=512).retrieve(
                entity_id="core", query_terms=("incidente", "rede"),
            )
            self.assertEqual(3, len(result))
            self.assertTrue(all(item["entity_id"] == "core" for item in result))
            self.assertLessEqual(len(str(result).encode("utf-8")), 512)
            store.close()


if __name__ == "__main__":
    unittest.main()
