import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"
WORKFLOW = ROOT / ".github" / "workflows" / "foundation-ci.yml"


class A1EmpacotamentoTests(unittest.TestCase):
    def test_instalador_inclui_a1_sem_ativar_servico(self):
        texto = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        for obrigatorio in (
            "modelo_afetivo.py", "configuracao_afetiva.py", "decaimento_afetivo.py",
            "motor_afetivo.py", "persistencia_afetiva.py", "config_afetiva.json",
        ):
            self.assertIn(obrigatorio, texto)
        self.assertNotIn("systemctl enable", texto.lower())
        self.assertNotIn("systemctl start", texto.lower())

    def test_ci_compila_valida_e_marca_a1(self):
        texto = WORKFLOW.read_text(encoding="utf-8")
        for obrigatorio in (
            "modelo_afetivo.py", "configuracao_afetiva.py", "decaimento_afetivo.py",
            "motor_afetivo.py", "persistencia_afetiva.py", "config_afetiva.json",
            "DEVEX_HOMELAB_ATLAS_AFETIVO_A1_PASS",
        ):
            self.assertIn(obrigatorio, texto)
