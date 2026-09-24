"""Testes do Memory Graph — grafo de entidades e relações tipadas."""
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.memory_graph import (
    Entity,
    EntityType,
    MemoryGraph,
    MemoryGraphError,
    Relation,
    RelationType,
)


NOW = "2026-09-22T12:00:00+00:00"
LATER = "2026-09-22T13:00:00+00:00"


def _entity(eid, etype=EntityType.PROJECT, name="test", **kw):
    return Entity(eid, etype, name, created_at=NOW, updated_at=NOW, **kw)


def _relation(src, tgt, rtype=RelationType.RELATED_TO, **kw):
    return Relation(src, tgt, rtype, created_at=NOW, **kw)


class EntityModelTests(unittest.TestCase):
    def test_entity_valida_bounds(self):
        with self.assertRaises(ValueError):
            Entity("", EntityType.PROJECT, "x", created_at=NOW)
        with self.assertRaises(ValueError):
            Entity("e1", EntityType.PROJECT, "", created_at=NOW)
        with self.assertRaises(ValueError):
            Entity("e1", EntityType.PROJECT, "x", created_at=NOW, importance=1.5)

    def test_entity_normaliza_timestamps(self):
        e = Entity("e1", EntityType.NODE, "core", created_at="2026-09-22T09:00:00-03:00")
        self.assertIn("+00:00", e.created_at)

    def test_relation_valida_bounds(self):
        with self.assertRaises(ValueError):
            Relation("", "t1", RelationType.OWNS, created_at=NOW)
        with self.assertRaises(ValueError):
            Relation("s1", "t1", RelationType.OWNS, weight=11.0, created_at=NOW)


class MemoryGraphCRUDTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.graph = MemoryGraph(Path(self.tmp.name) / "graph.db")

    def tearDown(self):
        self.graph.close()
        self.tmp.cleanup()

    def test_add_and_get_entity(self):
        e = _entity("proj:l2jtoren", name="L2jToren", description="Gameserver Interlude")
        self.graph.add_entity(e)
        got = self.graph.get_entity("proj:l2jtoren")
        self.assertIsNotNone(got)
        self.assertEqual("L2jToren", got.name)
        self.assertEqual(EntityType.PROJECT, got.entity_type)

    def test_get_nonexistent_returns_none(self):
        self.assertIsNone(self.graph.get_entity("nonexistent"))

    def test_add_entity_upsert(self):
        e1 = _entity("node:core", EntityType.NODE, "Core", importance=0.5)
        self.graph.add_entity(e1)
        e2 = _entity("node:core", EntityType.NODE, "Core Updated", importance=0.9)
        self.graph.add_entity(e2)
        got = self.graph.get_entity("node:core")
        self.assertEqual("Core Updated", got.name)
        self.assertAlmostEqual(0.9, got.importance)

    def test_list_entities_by_type(self):
        self.graph.add_entity(_entity("proj:a", name="A"))
        self.graph.add_entity(_entity("proj:b", name="B"))
        self.graph.add_entity(_entity("node:c", EntityType.NODE, "C"))
        projs = self.graph.list_entities(entity_type=EntityType.PROJECT)
        self.assertEqual(2, len(projs))
        all_entities = self.graph.list_entities()
        self.assertEqual(3, len(all_entities))

    def test_delete_entity_removes_relations(self):
        self.graph.add_entity(_entity("a", name="A"))
        self.graph.add_entity(_entity("b", name="B"))
        self.graph.add_relation(_relation("a", "b", RelationType.OWNS))
        self.assertTrue(self.graph.delete_entity("a"))
        self.assertIsNone(self.graph.get_entity("a"))
        self.assertEqual(0, self.graph.relation_count())

    def test_search_entities(self):
        self.graph.add_entity(_entity("p1", name="L2jToren Gameserver"))
        self.graph.add_entity(_entity("p2", name="DevEx HomeLab"))
        results = self.graph.search_entities("L2j")
        self.assertEqual(1, len(results))
        self.assertEqual("p1", results[0].entity_id)

    def test_entity_with_properties(self):
        e = _entity("node:pentium", EntityType.NODE, "Pentium",
                     properties={"role": "control", "ip": "100.107.230.78"})
        self.graph.add_entity(e)
        got = self.graph.get_entity("node:pentium")
        self.assertEqual("control", got.properties["role"])


class RelationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.graph = MemoryGraph(Path(self.tmp.name) / "graph.db")
        self.graph.add_entity(_entity("proj:l2j", name="L2jToren"))
        self.graph.add_entity(_entity("node:core", EntityType.NODE, "Core"))
        self.graph.add_entity(_entity("node:pentium", EntityType.NODE, "Pentium"))

    def tearDown(self):
        self.graph.close()
        self.tmp.cleanup()

    def test_add_and_get_relations(self):
        self.graph.add_relation(_relation("proj:l2j", "node:core", RelationType.RUNS_ON))
        rels = self.graph.get_relations("proj:l2j", direction="outgoing")
        self.assertEqual(1, len(rels))
        self.assertEqual(RelationType.RUNS_ON, rels[0].relation_type)

    def test_incoming_relations(self):
        self.graph.add_relation(_relation("proj:l2j", "node:core", RelationType.RUNS_ON))
        incoming = self.graph.get_relations("node:core", direction="incoming")
        self.assertEqual(1, len(incoming))

    def test_both_directions(self):
        self.graph.add_relation(_relation("proj:l2j", "node:core", RelationType.RUNS_ON))
        self.graph.add_relation(_relation("node:pentium", "proj:l2j", RelationType.MONITORS))
        both = self.graph.get_relations("proj:l2j", direction="both")
        self.assertEqual(2, len(both))

    def test_filter_by_relation_type(self):
        self.graph.add_relation(_relation("proj:l2j", "node:core", RelationType.RUNS_ON))
        self.graph.add_relation(_relation("proj:l2j", "node:pentium", RelationType.MONITORS))
        runs = self.graph.get_relations(
            "proj:l2j", direction="outgoing", relation_type=RelationType.RUNS_ON
        )
        self.assertEqual(1, len(runs))

    def test_remove_relation(self):
        self.graph.add_relation(_relation("proj:l2j", "node:core", RelationType.RUNS_ON))
        self.assertTrue(self.graph.remove_relation("proj:l2j", "node:core", RelationType.RUNS_ON))
        self.assertEqual(0, self.graph.relation_count())

    def test_relation_upsert_updates_weight(self):
        self.graph.add_relation(_relation("proj:l2j", "node:core", RelationType.RUNS_ON, weight=1.0))
        self.graph.add_relation(_relation("proj:l2j", "node:core", RelationType.RUNS_ON, weight=5.0))
        rels = self.graph.get_relations("proj:l2j", direction="outgoing")
        self.assertEqual(1, len(rels))
        self.assertAlmostEqual(5.0, rels[0].weight)


class GraphTraversalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.graph = MemoryGraph(Path(self.tmp.name) / "graph.db")
        # Build a small graph: L2j -> Core -> Pentium, L2j -> DevEx
        for eid, etype, name in [
            ("proj:l2j", EntityType.PROJECT, "L2jToren"),
            ("proj:devex", EntityType.PROJECT, "DevEx HomeLab"),
            ("node:core", EntityType.NODE, "Core"),
            ("node:pentium", EntityType.NODE, "Pentium"),
            ("dec:container-first", EntityType.DECISION, "Container-First Policy"),
        ]:
            self.graph.add_entity(_entity(eid, etype, name))
        self.graph.add_relation(_relation("proj:l2j", "node:core", RelationType.RUNS_ON))
        self.graph.add_relation(_relation("node:core", "node:pentium", RelationType.DEPENDS_ON))
        self.graph.add_relation(_relation("proj:l2j", "proj:devex", RelationType.RELATED_TO))
        self.graph.add_relation(_relation("proj:devex", "dec:container-first", RelationType.DECIDED_BY))

    def tearDown(self):
        self.graph.close()
        self.tmp.cleanup()

    def test_neighbors_depth_1(self):
        neighbors = self.graph.query_neighbors("proj:l2j", depth=1)
        ids = {e.entity_id for e in neighbors}
        self.assertIn("node:core", ids)
        self.assertIn("proj:devex", ids)
        self.assertNotIn("node:pentium", ids)

    def test_neighbors_depth_2(self):
        neighbors = self.graph.query_neighbors("proj:l2j", depth=2)
        ids = {e.entity_id for e in neighbors}
        self.assertIn("node:pentium", ids)
        self.assertIn("dec:container-first", ids)

    def test_neighbors_with_type_filter(self):
        neighbors = self.graph.query_neighbors(
            "proj:l2j", depth=1, relation_type=RelationType.RUNS_ON
        )
        ids = {e.entity_id for e in neighbors}
        self.assertIn("node:core", ids)
        self.assertNotIn("proj:devex", ids)

    def test_query_path_found(self):
        path = self.graph.query_path("proj:l2j", "node:pentium")
        self.assertIsNotNone(path)
        self.assertEqual("proj:l2j", path[0])
        self.assertEqual("node:pentium", path[-1])
        self.assertLessEqual(len(path), 3)

    def test_query_path_same_node(self):
        path = self.graph.query_path("proj:l2j", "proj:l2j")
        self.assertEqual(("proj:l2j",), path)

    def test_query_path_not_found(self):
        self.graph.add_entity(_entity("isolated", name="Isolated"))
        path = self.graph.query_path("proj:l2j", "isolated")
        self.assertIsNone(path)


class GraphPersistenceTests(unittest.TestCase):
    def test_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "graph.db"
            g1 = MemoryGraph(path)
            g1.add_entity(_entity("proj:x", name="X"))
            g1.add_relation(_relation("proj:x", "proj:x", RelationType.RELATED_TO))
            g1.close()

            g2 = MemoryGraph(path)
            self.assertIsNotNone(g2.get_entity("proj:x"))
            self.assertEqual(1, g2.entity_count())
            self.assertEqual(1, g2.relation_count())
            g2.close()


if __name__ == "__main__":
    unittest.main()
