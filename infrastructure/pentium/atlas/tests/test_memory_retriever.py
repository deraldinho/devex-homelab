import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.memory_graph import (
    Entity,
    EntityType,
    MemoryGraph,
    Relation,
    RelationType,
)
from infrastructure.pentium.atlas.memory_model import MemoryLayer, MemoryRecord
from infrastructure.pentium.atlas.memory_preference_tracker import (
    PreferenceSignal,
    PreferenceTracker,
)
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

    def test_grafo_proximidade_da_boost(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.db"
            store = MemoryStore(db_path)
            graph = MemoryGraph(db_path)

            # Entidades conectadas: x99 -> runs_on -> L2jToren
            graph.add_entity(Entity("node:x99", EntityType.NODE, "x99"))
            graph.add_entity(Entity("project:l2j", EntityType.PROJECT, "L2jToren"))
            graph.add_relation(Relation("project:l2j", "node:x99", RelationType.RUNS_ON))

            # Memórias: uma de pentium (desconectado), uma de node:x99 (conectado a project:l2j)
            store.save(MemoryRecord(
                "m_pentium", MemoryLayer.SEMANTIC, "2026-09-05T20:00:00+00:00",
                "node:pentium", "Controle Pentium", 0.5, 0.5, 1, "observation",
            ))
            store.save(MemoryRecord(
                "m_x99", MemoryLayer.SEMANTIC, "2026-09-05T20:00:00+00:00",
                "node:x99", "Host x99", 0.5, 0.5, 1, "observation",
            ))

            retriever = MemoryRetriever(store, graph=graph, max_items=2)
            # Buscar por entidade project:l2j -> m_x99 deve vir antes por ser vizinho
            results = retriever.retrieve(entity_id="project:l2j")
            self.assertTrue(len(results) >= 1)
            self.assertEqual(results[0]["memory_id"], "m_x99")
            graph.close()
            store.close()

    def test_retrieve_graph_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.db"
            store = MemoryStore(db_path)
            graph = MemoryGraph(db_path)

            graph.add_entity(Entity(
                "project:l2jtoren", EntityType.PROJECT, "L2jToren",
                description="Servidor Lineage 2 High Five em Java",
            ))
            graph.add_entity(Entity(
                "node:x99", EntityType.NODE, "x99",
                description="Host de alta performance para gameserver",
            ))
            graph.add_relation(Relation("project:l2jtoren", "node:x99", RelationType.RUNS_ON))

            retriever = MemoryRetriever(store, graph=graph)
            ctx = retriever.retrieve_graph_context("project:l2jtoren", limit=5)
            self.assertGreaterEqual(len(ctx), 2)
            ids = [e["entity_id"] for e in ctx]
            self.assertIn("project:l2jtoren", ids)
            self.assertIn("node:x99", ids)
            graph.close()
            store.close()

    def test_preference_tracker_boost(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.db"
            store = MemoryStore(db_path)
            pref_path = Path(tmp) / "pref.json"
            tracker = PreferenceTracker(pref_path)
            tracker.record(PreferenceSignal("topic", "l2jtoren", 1.0, "2026-09-22T12:00:00+00:00"))

            store.save(MemoryRecord(
                "m_other", MemoryLayer.SEMANTIC, "2026-09-05T20:00:00+00:00",
                "other", "Notas gerais", 0.5, 0.5, 1, "human",
            ))
            store.save(MemoryRecord(
                "m_pref", MemoryLayer.SEMANTIC, "2026-09-05T20:00:00+00:00",
                "other", "Arquitetura L2jToren", 0.5, 0.5, 1, "human",
            ))

            retriever = MemoryRetriever(store, preference_tracker=tracker, max_items=2)
            results = retriever.retrieve(query_terms=("l2jtoren",))
            self.assertEqual(results[0]["memory_id"], "m_pref")
            store.close()


if __name__ == "__main__":
    unittest.main()
