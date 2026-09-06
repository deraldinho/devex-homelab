import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


class C5EmpacotamentoTests(unittest.TestCase):
    def test_instalador_inclui_harness_runner_orquestrador_e_evaluator_sem_certificar_fisicamente(self):
        texto = (ROOT / "infrastructure/pentium/atlas/install-user.sh").read_text(encoding="utf-8")
        self.assertIn("certificacao_cognitiva.py", texto)
        self.assertIn("sampler_linux_cognitivo.py", texto)
        self.assertIn("fontes_fisicas_cognitivas.py", texto)
        self.assertIn("c5_physical_runner.py", texto)
        self.assertIn("c5_physical_orchestrator.py", texto)
        self.assertIn("c5_physical_evaluator.py", texto)
        self.assertIn("prompt_cognitivo.py", texto)
        self.assertIn("ATLAS_COGNITIVO_C5_HARNESS_INSTALL_PASS", texto)
        self.assertIn("ATLAS_COGNITIVO_C5_HARDENING_INSTALL_PASS", texto)
        self.assertNotIn("ATLAS_COGNITIVO_C5_PHYSICAL_PASS", texto)

    def test_ci_valida_hardening_e_evaluator_mas_nao_emite_certificacao_fisica(self):
        texto = (ROOT / ".github/workflows/foundation-ci.yml").read_text(encoding="utf-8")
        linhas = [linha.strip() for linha in texto.splitlines()]
        self.assertIn("certificacao_cognitiva.py", texto)
        self.assertIn("sampler_linux_cognitivo.py", texto)
        self.assertIn("fontes_fisicas_cognitivas.py", texto)
        self.assertIn("c5_physical_runner.py", texto)
        self.assertIn("c5_physical_orchestrator.py", texto)
        self.assertIn("c5_physical_evaluator.py", texto)
        self.assertIn("prompt_cognitivo.py", texto)
        self.assertIn("echo 'DEVEX_HOMELAB_ATLAS_COGNITIVO_C5_HARNESS_PASS'", linhas)
        self.assertIn("echo 'DEVEX_HOMELAB_ATLAS_COGNITIVO_C5_HARDENING_PASS'", linhas)
        self.assertNotIn("ATLAS_COGNITIVO_C5_PHYSICAL_PASS", texto)


if __name__ == "__main__":
    unittest.main()
