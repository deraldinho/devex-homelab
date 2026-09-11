import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]


class LegacyLlamaRemovalTests(unittest.TestCase):
    def test_backend_local_legado_nao_existe_mais(self):
        legacy = (
            "config_llm.json",
            "config_llama_server.json",
            "configuracao_llm.py",
            "llama_cpp_backend.py",
            "llama_cpp_resident_backend.py",
            "llama_server_runtime.py",
        )
        for name in legacy:
            self.assertFalse((ROOT / name).exists(), name)

    def test_installer_e_ci_nao_reintroduzem_legado(self):
        texts = [
            (ROOT / "install-user.sh").read_text(encoding="utf-8"),
            (REPO / ".github/workflows/foundation-ci.yml").read_text(encoding="utf-8"),
        ]
        for text in texts:
            for token in ("config_llm.json", "config_llama_server.json", "llama_cpp_backend.py",
                          "llama_cpp_resident_backend.py", "llama_server_runtime.py"):
                self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
