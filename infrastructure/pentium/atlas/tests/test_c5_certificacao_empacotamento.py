import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


class C5EmpacotamentoTests(unittest.TestCase):
    def test_instalador_inclui_campanha_completa_sem_certificar_fisicamente(self):
        texto = (ROOT / "infrastructure/pentium/atlas/install-user.sh").read_text(encoding="utf-8")
        for arquivo in (
            "certificacao_cognitiva.py",
            "sampler_linux_cognitivo.py",
            "fontes_fisicas_cognitivas.py",
            "c5_physical_runner.py",
            "c5_physical_orchestrator.py",
            "c5_physical_evaluator.py",
            "c5_physical_campaign.py",
            "c5_observation_probe.py",
            "prompt_cognitivo.py",
        ):
            self.assertIn(arquivo, texto)
        self.assertIn("ATLAS_COGNITIVO_C5_HARNESS_INSTALL_PASS", texto)
        self.assertIn("ATLAS_COGNITIVO_C5_HARDENING_INSTALL_PASS", texto)
        self.assertNotIn("ATLAS_COGNITIVO_C5_PHYSICAL_PASS", texto)

    def test_ci_valida_campanha_completa_mas_nao_emite_certificacao_fisica(self):
        texto = (ROOT / ".github/workflows/foundation-ci.yml").read_text(encoding="utf-8")
        linhas = [linha.strip() for linha in texto.splitlines()]
        for arquivo in (
            "certificacao_cognitiva.py",
            "sampler_linux_cognitivo.py",
            "fontes_fisicas_cognitivas.py",
            "c5_physical_runner.py",
            "c5_physical_orchestrator.py",
            "c5_physical_evaluator.py",
            "c5_physical_campaign.py",
            "c5_observation_probe.py",
            "prompt_cognitivo.py",
        ):
            self.assertIn(arquivo, texto)
        self.assertIn("echo 'DEVEX_HOMELAB_ATLAS_COGNITIVO_C5_HARNESS_PASS'", linhas)
        self.assertIn("echo 'DEVEX_HOMELAB_ATLAS_COGNITIVO_C5_HARDENING_PASS'", linhas)
        self.assertNotIn("ATLAS_COGNITIVO_C5_PHYSICAL_PASS", texto)


if __name__ == "__main__":
    unittest.main()
