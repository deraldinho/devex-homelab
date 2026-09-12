import json
import os
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.workspace_broker import WorkspaceBroker, WorkspaceBrokerError
from infrastructure.pentium.atlas.workspace_policy import WorkspacePolicy


class WorkspaceBrokerTests(unittest.TestCase):
    def _broker(self, root, **policy_overrides):
        return WorkspaceBroker(Path(root), WorkspacePolicy(**policy_overrides))

    def test_write_cria_arquivo_atomico_com_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            broker = self._broker(tmp)
            record = broker.write("notes", "core.md", "estado do core", reason="self_work", source_intent="i-1")
            path = Path(tmp) / "notes" / "core.md"
            self.assertEqual("estado do core", path.read_text(encoding="utf-8"))
            self.assertEqual("notes/core.md", record.path)
            self.assertEqual("atlas", record.created_by)
            self.assertEqual("self_work", record.reason)
            self.assertEqual("i-1", record.source_intent)
            self.assertTrue(record.sha256)
            self.assertFalse(path.with_name(path.name + ".tmp").exists())
            if os.name != "nt":
                self.assertEqual(0o600, path.stat().st_mode & 0o777)

    def test_append_respeita_limite_por_arquivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            broker = self._broker(tmp, max_file_bytes=8)
            broker.write("notes", "x.txt", "1234")
            with self.assertRaisesRegex(WorkspaceBrokerError, "file_size_limit"):
                broker.append("notes", "x.txt", "56789")

    def test_quota_total_e_contagem_sao_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            broker = self._broker(tmp, max_total_bytes=8, max_files=1)
            broker.write("notes", "a.txt", "1234")
            with self.assertRaisesRegex(WorkspaceBrokerError, "file_count_limit"):
                broker.write("notes", "b.txt", "1")
            broker.write("notes", "a.txt", "12345678")
            with self.assertRaisesRegex(WorkspaceBrokerError, "quota_limit"):
                broker.append("notes", "a.txt", "9")

    def test_trash_e_restore_sao_recuperaveis(self):
        with tempfile.TemporaryDirectory() as tmp:
            broker = self._broker(tmp)
            broker.write("ideas", "idea.md", "uma ideia")
            trashed = broker.trash("ideas", "idea.md", reason="obsolete")
            self.assertFalse((Path(tmp) / "ideas" / "idea.md").exists())
            self.assertTrue((Path(tmp) / trashed.trash_path).exists())
            restored = broker.restore(trashed.trash_id)
            self.assertEqual("ideas/idea.md", restored.path)
            self.assertEqual("uma ideia", (Path(tmp) / "ideas" / "idea.md").read_text(encoding="utf-8"))

    def test_audit_e_manifest_sao_append_only_e_legiveis(self):
        with tempfile.TemporaryDirectory() as tmp:
            broker = self._broker(tmp)
            broker.write("notes", "a.md", "a", reason="self_work")
            broker.append("notes", "a.md", "b", reason="self_work")
            audit = (Path(tmp) / ".system" / "audit.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(2, len(audit))
            self.assertEqual(["write", "append"], [json.loads(line)["operation"] for line in audit])
            manifest = json.loads((Path(tmp) / ".system" / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn("notes/a.md", manifest["files"])

    def test_nao_existe_api_de_delete_permanente(self):
        with tempfile.TemporaryDirectory() as tmp:
            broker = self._broker(tmp)
            self.assertFalse(hasattr(broker, "delete"))
            self.assertFalse(hasattr(broker, "purge"))


if __name__ == "__main__":
    unittest.main()
