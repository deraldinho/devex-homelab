import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"
WORKFLOW = ROOT / ".github" / "workflows" / "foundation-ci.yml"


class A2EmpacotamentoTests(unittest.TestCase):
    def test_instalador_inclui_modulos_a2_sem_ativar_servico(self):
        texto = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        for obrigatorio in (
            "modelo_contexto_afetivo.py",
            "contexto_afetivo.py",
            "persistencia_contexto_afetivo.py",
            "ATLAS_AFETIVO_A2_INSTALL_PASS",
        ):
            self.assertIn(obrigatorio, texto)
        self.assertNotIn("systemctl enable", texto.lower())
        self.assertNotIn("systemctl start", texto.lower())

    def test_ci_compila_e_marca_a2(self):
        texto = WORKFLOW.read_text(encoding="utf-8")
        for obrigatorio in (
            "modelo_contexto_afetivo.py",
            "contexto_afetivo.py",
            "persistencia_contexto_afetivo.py",
            "DEVEX_HOMELAB_ATLAS_AFETIVO_A2_PASS",
        ):
            self.assertIn(obrigatorio, texto)
