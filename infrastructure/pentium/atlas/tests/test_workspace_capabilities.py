import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.capability_registry import atlas_capability_registry
from infrastructure.pentium.atlas.policy_capabilities import PolicyCapabilities
from infrastructure.pentium.atlas.workspace_broker import WorkspaceBroker
from infrastructure.pentium.atlas.workspace_capability_executor import WorkspaceCapabilityExecutor
from infrastructure.pentium.atlas.workspace_policy import WorkspacePolicy


class WorkspaceCapabilitiesTests(unittest.TestCase):
    def test_registry_expoe_apenas_capabilities_workspace_especificas(self):
        registry = atlas_capability_registry()
        names = set(registry.listar())
        expected = {
            "workspace_status", "workspace_list", "workspace_read", "workspace_search",
            "workspace_create_note", "workspace_write", "workspace_append", "workspace_mkdir",
            "workspace_move", "workspace_archive", "workspace_trash", "workspace_restore", "workspace_purge",
        }
        self.assertTrue(expected <= names)
        self.assertNotIn("filesystem_read", names)
        self.assertNotIn("filesystem_write", names)
        self.assertNotIn("shell", names)
        self.assertNotIn("execute_file", names)
        self.assertEqual("DESTRUCTIVE", registry.obter("workspace_purge").nivel)

    def test_policy_permite_auto_workspace_bounded_mas_purge_exige_confirmacao(self):
        registry = atlas_capability_registry()
        policy = PolicyCapabilities(
            registry,
            read_auto_allow=("workspace_status", "workspace_list", "workspace_read", "workspace_search"),
            auto_unscoped_control_allow=("workspace_write", "workspace_append", "workspace_trash", "workspace_restore"),
        )
        write = policy.avaliar("workspace_write", {"area": "notes", "path": "a.md", "content": "x"})
        self.assertTrue(write.autorizada)
        self.assertEqual("AUTO", write.autonomia)
        purge = policy.avaliar("workspace_purge", {"trash_id": "x"})
        self.assertFalse(purge.autorizada)
        self.assertTrue(purge.requer_confirmacao)
        purge_confirmed = policy.avaliar("workspace_purge", {"trash_id": "x"}, confirmacao_humana=True)
        self.assertTrue(purge_confirmed.autorizada)

    def test_executor_delega_write_read_trash_restore_sem_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            broker = WorkspaceBroker(Path(tmp), WorkspacePolicy())
            executor = WorkspaceCapabilityExecutor(broker)
            executor("workspace_write", {"area": "notes", "path": "a.md", "content": "hello"}, None, None)
            self.assertEqual("hello", executor("workspace_read", {"area": "notes", "path": "a.md"}, None, None))
            trashed = executor("workspace_trash", {"area": "notes", "path": "a.md"}, None, None)
            restored = executor("workspace_restore", {"trash_id": trashed.trash_id}, None, None)
            self.assertEqual("notes/a.md", restored.path)
            with self.assertRaises(PermissionError):
                executor("shell", {"command": "whoami"}, None, None)

    def test_parametros_invalidos_sao_rejeitados_pela_policy(self):
        registry = atlas_capability_registry()
        policy = PolicyCapabilities(registry, auto_unscoped_control_allow=("workspace_write",))
        decision = policy.avaliar("workspace_write", {"area": "notes", "path": "a.md"})
        self.assertFalse(decision.autorizada)
        self.assertEqual("parametros_invalidos", decision.razao)


if __name__ == "__main__":
    unittest.main()
