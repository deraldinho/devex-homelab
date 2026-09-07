import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"


class C1EmpacotamentoTests(unittest.TestCase):
    def test_instalador_inclui_c1_sem_iniciar_servico_ou_llm(self):
        texto = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        for nome in (
            "modelo_contexto_cognitivo.py", "configuracao_cognitiva.py",
            "contexto_cognitivo.py", "politica_ativacao_cognitiva.py",
            "config_cognitiva.json", "ATLAS_COGNITIVO_C1_INSTALL_PASS",
        ):
            self.assertIn(nome, texto)
        for proibido in ("llama.cpp", "systemctl enable", "systemctl start"):
            self.assertNotIn(proibido, texto)

    def test_ci_compila_valida_e_marca_c1(self):
        texto = (ROOT / ".github" / "workflows" / "foundation-ci.yml").read_text(encoding="utf-8")
        self.assertIn("DEVEX_HOMELAB_ATLAS_COGNITIVO_C1_PASS", texto)
        self.assertIn("config_cognitiva.json", texto)
        for nome in ("modelo_contexto_cognitivo.py", "configuracao_cognitiva.py", "contexto_cognitivo.py", "politica_ativacao_cognitiva.py"):
            self.assertIn(nome, texto)


if __name__ == "__main__": unittest.main()
