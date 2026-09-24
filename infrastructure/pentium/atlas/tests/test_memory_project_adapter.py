"""Testes do Memory Project Adapter."""
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.memory_graph import (
    EntityType,
    MemoryGraph,
    RelationType,
)
from infrastructure.pentium.atlas.memory_project_adapter import (
    MemoryProjectAdapter,
    ProjectEvent,
)


NOW = "2026-09-22T12:00:00+00:00"


class ProjectEventModelTests(unittest.TestCase):
    def test_event_valida_campos(self):
        with self.assertRaises(ValueError):
            ProjectEvent("", "commit", "test")
        with self.assertRaises(ValueError):
            ProjectEvent("l2j", "", "test")
        with self.assertRaises(ValueError):
            ProjectEvent("l2j", "commit", "")


class ProjectAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.graph = MemoryGraph(Path(self.tmp.name) / "graph.db")
        self.adapter = MemoryProjectAdapter(self.graph)

    def tearDown(self):
        self.graph.close()
        self.tmp.cleanup()

    def test_process_commit_creates_project_entity(self):
        event = ProjectEvent(
            project_id="l2jtoren",
            event_type="commit",
            title="feat: add gameserver metrics",
            repository="deraldinho/L2jToren",
            timestamp=NOW,
        )
        affected = self.adapter.process_event(event)
        self.assertIn("proj:l2jtoren", affected)
        proj = self.graph.get_entity("proj:l2jtoren")
        self.assertIsNotNone(proj)
        self.assertEqual(EntityType.PROJECT, proj.entity_type)

    def test_process_creates_repository_with_ownership(self):
        event = ProjectEvent(
            "l2jtoren", "commit", "fix: bug",
            repository="deraldinho/L2jToren", timestamp=NOW,
        )
        self.adapter.process_event(event)
        repo = self.graph.get_entity("repo:deraldinho/L2jToren")
        self.assertIsNotNone(repo)
        rels = self.graph.get_relations("proj:l2jtoren", direction="outgoing",
                                         relation_type=RelationType.OWNS)
        self.assertEqual(1, len(rels))

    def test_process_detects_decision(self):
        event = ProjectEvent(
            "devex-homelab", "pr_merged",
            title="Decisão: usar container-first para todos os runners",
            description="Detalhes da decisão arquitetural",
            timestamp=NOW,
        )
        affected = self.adapter.process_event(event)
        decisions = [a for a in affected if a.startswith("dec:")]
        self.assertGreaterEqual(len(decisions), 1)
        dec = self.graph.get_entity(decisions[0])
        self.assertEqual(EntityType.DECISION, dec.entity_type)

    def test_process_detects_patterns(self):
        event = ProjectEvent(
            "devex-homelab", "commit",
            title="Apply container-first and TDD policy",
            timestamp=NOW,
        )
        affected = self.adapter.process_event(event)
        pat_ids = [a for a in affected if a.startswith("pattern:")]
        self.assertGreaterEqual(len(pat_ids), 1)
        pat_names = {self.graph.get_entity(p).name for p in pat_ids}
        self.assertTrue(pat_names & {"container-first", "tdd"})

    def test_idempotent_project_creation(self):
        event = ProjectEvent("l2jtoren", "commit", "fix: x", timestamp=NOW)
        self.adapter.process_event(event)
        self.adapter.process_event(event)
        projs = self.graph.list_entities(entity_type=EntityType.PROJECT)
        self.assertEqual(1, len(projs))


class BaselineTests(unittest.TestCase):
    def test_ensure_homelab_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph = MemoryGraph(Path(tmp) / "graph.db")
            adapter = MemoryProjectAdapter(graph)
            affected = adapter.ensure_homelab_baseline()
            self.assertIn("proj:devex-homelab", affected)
            self.assertIn("proj:l2jtoren", affected)
            self.assertIn("node:core", affected)
            self.assertIn("node:pentium", affected)
            self.assertIn("node:x99", affected)
            self.assertIn("person:operador", affected)

            # Verificar relações
            rels = graph.get_relations("proj:l2jtoren", direction="outgoing",
                                        relation_type=RelationType.RUNS_ON)
            self.assertGreaterEqual(len(rels), 1)

            # Idempotente
            affected2 = adapter.ensure_homelab_baseline()
            self.assertEqual(0, len(affected2))

            graph.close()


if __name__ == "__main__":
    unittest.main()
