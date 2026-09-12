import os
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.workspace_policy import (
    WorkspacePolicy,
    WorkspacePolicyError,
    resolve_workspace_path,
)


class WorkspacePolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = WorkspacePolicy()

    def test_resolve_path_valido_fica_dentro_da_area(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = resolve_workspace_path(root, "notes", "runner-core.md", self.policy)
            self.assertEqual(root / "notes" / "runner-core.md", result)

    def test_rejeita_caminho_absoluto(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(WorkspacePolicyError, "absolute_path_forbidden"):
                resolve_workspace_path(Path(tmp), "notes", str(Path(tmp) / "x.md"), self.policy)

    def test_rejeita_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(WorkspacePolicyError, "path_traversal_forbidden"):
                resolve_workspace_path(Path(tmp), "notes", "../outside.md", self.policy)

    def test_rejeita_area_desconhecida(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(WorkspacePolicyError, "area_forbidden"):
                resolve_workspace_path(Path(tmp), "ssh", "id_rsa.md", self.policy)

    def test_rejeita_extensao_executavel(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(WorkspacePolicyError, "extension_forbidden"):
                resolve_workspace_path(Path(tmp), "scratch", "run.sh", self.policy)

    def test_rejeita_symlink_que_escapa_da_raiz(self):
        if os.name == "nt":
            self.skipTest("symlink privilege is not reliable on Windows test hosts")
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            (root / "notes").mkdir()
            (root / "notes" / "escape").symlink_to(Path(outside), target_is_directory=True)
            with self.assertRaisesRegex(WorkspacePolicyError, "symlink_forbidden"):
                resolve_workspace_path(root, "notes", "escape/x.md", self.policy)

    def test_limites_padrao_correspondem_ao_contrato(self):
        self.assertEqual(134217728, self.policy.max_total_bytes)
        self.assertEqual(1048576, self.policy.max_file_bytes)
        self.assertEqual(2048, self.policy.max_files)


if __name__ == "__main__":
    unittest.main()
