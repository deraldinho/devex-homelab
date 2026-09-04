import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"


class A4EmpacotamentoTests(unittest.TestCase):
    def test_config_declara_politicas_a4(self):
        payload = json.loads((ATLAS / "config_foco_emocao.json").read_text(encoding="utf-8"))
        self.assertEqual(1, payload["schema_version"])
        self.assertGreater(payload["foco"]["capacidade_secundarios"], 0)
        self.assertGreaterEqual(payload["foco"]["margem_histerese"], 0.0)
        self.assertGreaterEqual(payload["emocao"]["capacidade_nuances"], 0)

    def test_instalador_inclui_modulos_e_gate_a4(self):
        texto = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        for nome in (
            "modelo_foco.py", "motor_foco.py", "emocao_derivada.py",
            "contexto_foco_emocao.py", "persistencia_foco_emocao.py",
            "config_foco_emocao.json", "ATLAS_AFETIVO_A4_INSTALL_PASS",
        ):
            self.assertIn(nome, texto)
        self.assertNotIn("systemctl enable", texto)
        self.assertNotIn("systemctl start", texto)

    def test_ci_compila_valida_e_marca_a4(self):
        texto = (ROOT / ".github" / "workflows" / "foundation-ci.yml").read_text(encoding="utf-8")
        for nome in (
            "modelo_foco.py", "motor_foco.py", "emocao_derivada.py",
            "contexto_foco_emocao.py", "persistencia_foco_emocao.py",
            "config_foco_emocao.json", "DEVEX_HOMELAB_ATLAS_AFETIVO_A4_PASS",
        ):
            self.assertIn(nome, texto)


if __name__ == "__main__":
    unittest.main()
