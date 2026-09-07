import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


class C4EmpacotamentoTests(unittest.TestCase):
    def test_instalador_inclui_modulos_c4_sem_executor(self):
        texto = (ROOT / "infrastructure/pentium/atlas/install-user.sh").read_text(encoding="utf-8")
        for nome in ("capability_registry.py", "policy_capabilities.py", "saida_cognitiva.py"):
            self.assertIn(nome, texto)
        self.assertNotIn("run_shell", texto)
        self.assertNotIn("ssh(command)", texto)

    def test_ci_compila_e_marca_c4(self):
        texto = (ROOT / ".github/workflows/foundation-ci.yml").read_text(encoding="utf-8")
        self.assertIn("capability_registry.py", texto)
        self.assertIn("policy_capabilities.py", texto)
        self.assertIn("saida_cognitiva.py", texto)
        linhas = [linha.strip() for linha in texto.splitlines()]
        self.assertIn("echo 'DEVEX_HOMELAB_ATLAS_COGNITIVO_C4_PASS'", linhas)
        self.assertNotIn("\\n            echo 'DEVEX_HOMELAB_ATLAS_COGNITIVO_C4_PASS'", texto)


if __name__ == "__main__":
    unittest.main()
