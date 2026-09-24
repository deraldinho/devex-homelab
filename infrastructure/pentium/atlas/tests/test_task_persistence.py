import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.self_work import SelfWorkRuntime, SelfWorkState
from infrastructure.pentium.atlas.task_capability_executor import TaskCapabilityExecutor
from infrastructure.pentium.atlas.task_store import SelfWorkStore


class TaskPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.tmp_dir.name)
        self.current_json = self.dir_path / "self-work-current.json"
        self.history_jsonl = self.dir_path / "self-work-history.jsonl"
        self.store = SelfWorkStore(self.current_json, self.history_jsonl)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_store_saves_and_restores_active_item(self):
        runtime = SelfWorkRuntime(ttl_s=300, store=self.store, id_factory=lambda: "task-100")
        item = runtime.propose("Auditar nós de infraestrutura", "infra", now="2026-09-20T18:00:00+00:00")
        runtime.activate(now="2026-09-20T18:00:01+00:00")
        runtime.begin_work(now="2026-09-20T18:00:02+00:00")

        self.assertTrue(self.current_json.is_file())

        # Simula restart de processo: novo runtime limpo conectado ao mesmo store
        new_runtime = SelfWorkRuntime(ttl_s=300, store=self.store)
        self.assertIsNone(new_runtime.current)
        restored = new_runtime.restore_from_store(now="2026-09-20T18:01:00+00:00")

        self.assertIsNotNone(restored)
        self.assertEqual("task-100", restored.item_id)
        self.assertEqual("Auditar nós de infraestrutura", restored.objective)
        self.assertEqual("infra", restored.area)
        self.assertEqual(SelfWorkState.WORKING, restored.state)

    def test_store_expires_stale_task_on_restore(self):
        runtime = SelfWorkRuntime(ttl_s=50, store=self.store, id_factory=lambda: "task-expired")
        runtime.propose("Auditoria rápida", "infra", now="2026-09-20T18:00:00+00:00")
        runtime.activate(now="2026-09-20T18:00:01+00:00")

        # Tenta restaurar 10 minutos depois (TTL expirado)
        new_runtime = SelfWorkRuntime(ttl_s=50, store=self.store)
        restored = new_runtime.restore_from_store(now="2026-09-20T18:10:00+00:00")
        self.assertIsNone(restored)

    def test_task_capability_executor_lifecycle(self):
        runtime = SelfWorkRuntime(ttl_s=300, store=self.store, id_factory=lambda: "task-live")
        executor = TaskCapabilityExecutor(runtime)

        # 1. Sem tarefa ativa
        status_idle = executor("task_status", {})
        self.assertFalse(status_idle["has_active_task"])
        self.assertEqual("IDLE", status_idle["status"])

        # 2. Cria tarefa
        created = executor("task_create", {"objective": "Verificar backups Restic", "area": "dr"})
        self.assertEqual("CREATED", created["status"])
        self.assertEqual("task-live", created["item_id"])

        # 3. Status da tarefa ativa
        status_active = executor("task_status", {})
        self.assertTrue(status_active["has_active_task"])
        self.assertEqual("WORKING", status_active["status"])
        self.assertEqual("Verificar backups Restic", status_active["objective"])

        # 4. Conclui tarefa
        done = executor("task_complete", {"reason": "verificacao_concluida_com_sucesso"})
        self.assertEqual("COMPLETED", done["status"])

        # 5. Volta para IDLE e gravou no histórico
        status_after = executor("task_status", {})
        self.assertFalse(status_after["has_active_task"])
        self.assertTrue(self.history_jsonl.is_file())
        history_lines = self.history_jsonl.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(1, len(history_lines))
        self.assertIn("Verificar backups Restic", history_lines[0])


if __name__ == "__main__":
    unittest.main()
