import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"
WORKFLOW = ROOT / ".github" / "workflows" / "foundation-ci.yml"


class A3EmpacotamentoTests(unittest.TestCase):
    def test_config_percepcao_declara_politica_fontes_e_topologia(self):
        payload = json.loads((ATLAS / "config_percepcao.json").read_text(encoding="utf-8"))
        self.assertEqual(1, payload["versao_esquema"])
        self.assertEqual(2, payload["politica"]["min_fontes_indisponiveis"])
        self.assertIn("core", payload["fontes"])
        self.assertIn(["core", "firewall"], payload["dependencias"])

    def test_instalador_inclui_a3_sem_ativar_servico(self):
        texto = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        for nome in (
            "modelo_percepcao.py", "percepcao.py", "adaptador_stimulus_percepcao.py",
            "grafo_dependencias.py", "modelo_incidente.py", "correlacionador_incidentes.py",
            "pipeline_percepcao_correlacao.py", "persistencia_percepcao_correlacao.py",
            "config_percepcao.json",
        ):
            self.assertIn(nome, texto)
        self.assertNotIn("systemctl enable", texto.lower())
        self.assertNotIn("systemctl start", texto.lower())

    def test_ci_compila_valida_e_marca_a3(self):
        texto = WORKFLOW.read_text(encoding="utf-8")
        for nome in (
            "modelo_percepcao.py", "percepcao.py", "adaptador_stimulus_percepcao.py",
            "grafo_dependencias.py", "modelo_incidente.py", "correlacionador_incidentes.py",
            "pipeline_percepcao_correlacao.py", "persistencia_percepcao_correlacao.py",
            "config_percepcao.json", "DEVEX_HOMELAB_ATLAS_AFETIVO_A3_PASS",
        ):
            self.assertIn(nome, texto)


if __name__ == "__main__":
    unittest.main()
