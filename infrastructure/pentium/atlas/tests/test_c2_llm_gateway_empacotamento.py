import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"


class C2EmpacotamentoTests(unittest.TestCase):
    def test_instalador_inclui_c2_sem_modelo_download_ou_start(self):
        texto = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        for nome in (
            "modelo_llm_gateway.py", "config_hermes.py", "hermes_adapter.py",
            "llm_gateway.py", "config_hermes.json", "ATLAS_COGNITIVO_C2_INSTALL_PASS",
        ):
            self.assertIn(nome, texto)
        for legado in ("configuracao_llm.py", "llama_cpp_backend.py", "config_llm.json"):
            self.assertNotIn(legado, texto)
        for proibido in ("curl ", "wget ", "systemctl enable", "systemctl start", ".gguf\""):
            self.assertNotIn(proibido, texto)

    def test_ci_compila_valida_e_marca_c2(self):
        texto = (ROOT / ".github" / "workflows" / "foundation-ci.yml").read_text(encoding="utf-8")
        self.assertIn("DEVEX_HOMELAB_ATLAS_COGNITIVO_C2_PASS", texto)
        self.assertIn("config_hermes.json", texto)
        self.assertIn("hermes_adapter.py", texto)


if __name__ == "__main__":
    unittest.main()
