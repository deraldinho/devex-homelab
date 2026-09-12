import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.workspace_index import WorkspaceIndex
from infrastructure.pentium.atlas.workspace_retriever import WorkspaceRetriever


class WorkspaceRetrieverTests(unittest.TestCase):
    def test_busca_local_encontra_por_titulo_e_conteudo(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = WorkspaceIndex(Path(tmp) / "index.sqlite3")
            index.upsert("notes/core.md", title="Core runner", digest="runner saudavel", content="reinicio controlado do runner core", sha256="a")
            index.upsert("notes/audio.md", title="Audio", digest="alsa", content="microfone interno", sha256="b")
            results = index.search("runner core", limit=5)
            self.assertEqual("notes/core.md", results[0]["path"])
            index.close()

    def test_upsert_mesmo_hash_e_estavel(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = WorkspaceIndex(Path(tmp) / "index.sqlite3")
            self.assertTrue(index.upsert("notes/a.md", title="A", digest="d", content="c", sha256="same"))
            self.assertFalse(index.upsert("notes/a.md", title="A", digest="d", content="c", sha256="same"))
            self.assertEqual(1, index.count())
            index.close()

    def test_retrieval_respeita_limite_de_itens_e_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = WorkspaceIndex(Path(tmp) / "index.sqlite3")
            for idx in range(5):
                index.upsert(f"notes/{idx}.md", title=f"Core {idx}", digest="core runner", content="x" * 500, sha256=str(idx))
            retriever = WorkspaceRetriever(index)
            result = retriever.retrieve("core", max_items=2, max_bytes=350)
            self.assertLessEqual(len(result), 2)
            self.assertLessEqual(len(str(result).encode("utf-8")), 500)
            index.close()

    def test_metadata_suficiente_nao_retorna_arquivo_completo(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = WorkspaceIndex(Path(tmp) / "index.sqlite3")
            content = "CONTEUDO_COMPLETO_" * 200
            index.upsert("projects/voice/status.md", title="Voice activation", digest="bloqueio de permissao ALSA", content=content, sha256="voice")
            retriever = WorkspaceRetriever(index)
            result = retriever.retrieve("Voice activation", max_items=3, max_bytes=1024)
            self.assertEqual("metadata", result[0]["level"])
            self.assertNotIn("CONTEUDO_COMPLETO_", str(result[0]))
            index.close()

    def test_remove_exclui_documento_do_indice(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = WorkspaceIndex(Path(tmp) / "index.sqlite3")
            index.upsert("notes/a.md", title="A", digest="core", content="runner", sha256="a")
            self.assertTrue(index.remove("notes/a.md"))
            self.assertEqual((), index.search("core", limit=5))
            index.close()


if __name__ == "__main__":
    unittest.main()
