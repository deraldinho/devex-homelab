"""Testes do Task Tracker."""
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.autonomy.task_tracker import (
    AtlasTask,
    TaskPriority,
    TaskSource,
    TaskStatus,
    TaskTracker,
)


class TaskModelTests(unittest.TestCase):
    def test_valida_campos(self):
        with self.assertRaises(ValueError):
            AtlasTask(task_id="", title="ok")
        with self.assertRaises(ValueError):
            AtlasTask(task_id="t1", title="")

    def test_terminal_states(self):
        t1 = AtlasTask(task_id="t1", title="test", status=TaskStatus.OPEN)
        self.assertFalse(t1.is_terminal)
        t2 = AtlasTask(task_id="t2", title="test", status=TaskStatus.COMPLETED)
        self.assertTrue(t2.is_terminal)
        t3 = AtlasTask(task_id="t3", title="test", status=TaskStatus.CANCELLED)
        self.assertTrue(t3.is_terminal)


class TaskTrackerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "tasks.json"
        self.tracker = TaskTracker(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_and_get(self):
        task = self.tracker.create(
            task_id="task-01",
            title="Verificar uso de disco no Pentium",
            priority=TaskPriority.HIGH,
            source=TaskSource.SELF_OBSERVATION,
            description="Disco /home acima de 85%",
        )
        self.assertEqual(task.task_id, "task-01")
        self.assertEqual(task.status, TaskStatus.OPEN)

        retrieved = self.tracker.get("task-01")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.title, "Verificar uso de disco no Pentium")

    def test_deduplication_by_source_ref(self):
        t1 = self.tracker.create(
            task_id="t1",
            title="Trend 1",
            source_ref="trend:x99:cpu",
        )
        t2 = self.tracker.create(
            task_id="t2",
            title="Trend 1 duplicate",
            source_ref="trend:x99:cpu",
        )
        self.assertEqual(t1.task_id, t2.task_id)
        self.assertEqual(self.tracker.task_count(open_only=True), 1)

    def test_update_status(self):
        self.tracker.create(task_id="t1", title="Tarefa 1")
        updated = self.tracker.update_status("t1", TaskStatus.IN_PROGRESS, "Iniciando")
        self.assertEqual(updated.status, TaskStatus.IN_PROGRESS)
        self.assertIn("Iniciando", updated.description)

        completed = self.tracker.update_status("t1", TaskStatus.COMPLETED, "Resolvido")
        self.assertEqual(completed.status, TaskStatus.COMPLETED)
        self.assertTrue(completed.completed_at)

        # Não deve permitir reabrir se já terminal
        res = self.tracker.update_status("t1", TaskStatus.OPEN)
        self.assertIsNone(res)

    def test_list_open_sorted_by_priority(self):
        self.tracker.create("low", "Low Task", priority=TaskPriority.LOW)
        self.tracker.create("crit", "Critical Task", priority=TaskPriority.CRITICAL)
        self.tracker.create("med", "Medium Task", priority=TaskPriority.MEDIUM)

        open_tasks = self.tracker.list_open()
        self.assertEqual([t.task_id for t in open_tasks], ["crit", "med", "low"])

    def test_max_open_limit(self):
        original_limit = self.tracker.MAX_OPEN
        self.tracker.MAX_OPEN = 2
        try:
            self.tracker.create("t1", "T1")
            self.tracker.create("t2", "T2")
            with self.assertRaises(OverflowError):
                self.tracker.create("t3", "T3")
        finally:
            self.tracker.MAX_OPEN = original_limit

    def test_suggest_from_trend_and_hypothesis(self):
        t_trend = self.tracker.suggest_from_trend("pentium:ram", "rising", "esgotamento em 4h")
        self.assertEqual(t_trend.source, TaskSource.TREND)
        self.assertEqual(t_trend.priority, TaskPriority.HIGH)

        t_hypo = self.tracker.suggest_from_hypothesis("hypo-01", "Verificar leak no log")
        self.assertEqual(t_hypo.source, TaskSource.HYPOTHESIS)

    def test_persistence(self):
        self.tracker.create("t1", "Persistida", priority=TaskPriority.HIGH)

        tracker2 = TaskTracker(self.db_path)
        t = tracker2.get("t1")
        self.assertIsNotNone(t)
        self.assertEqual(t.priority, TaskPriority.HIGH)


if __name__ == "__main__":
    unittest.main()
