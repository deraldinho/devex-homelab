import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"


class C3EmpacotamentoTests(unittest.TestCase):
    def test_instalador_inclui_reaction_loop_sem_start(self):
        texto = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        self.assertIn("reaction_loop_cognitivo.py", texto)
        self.assertIn("ATLAS_COGNITIVO_C3_INSTALL_PASS", texto)
        self.assertNotIn("systemctl start", texto)

    def test_ci_compila_e_marca_c3(self):
        texto = (ROOT / ".github" / "workflows" / "foundation-ci.yml").read_text(encoding="utf-8")
        self.assertIn("reaction_loop_cognitivo.py", texto)
        self.assertIn("DEVEX_HOMELAB_ATLAS_COGNITIVO_C3_PASS", texto)
