import json
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.pipeline_afetivo_observacional import carregar_config_observation_affective

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"


class ObservationAffectivePackagingTests(unittest.TestCase):
    def test_installer_inclui_pipeline_config_e_gate(self):
        texto = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        for nome in (
            "adaptador_impacto_afetivo.py",
            "pipeline_afetivo_observacional.py",
            "config_observation_affective.json",
            "ATLAS_OBSERVATION_AFFECTIVE_PIPELINE_INSTALL_PASS",
        ):
            self.assertIn(nome, texto)

    def test_config_e_versionada_e_bounded(self):
        cfg = json.loads((ATLAS / "config_observation_affective.json").read_text(encoding="utf-8"))
        self.assertEqual(1, cfg["schema_version"])
        for nome in ("stimulus_ids", "incidentes", "assuntos", "erros"):
            self.assertGreater(cfg["capacidades"][nome], 0)
            self.assertLessEqual(cfg["capacidades"][nome], 4096)
        self.assertGreater(cfg["janela_reincidencia_s"], 0)
        self.assertGreater(cfg["limite_repeticoes"], 0)

    def test_loader_materializa_config_do_pipeline_e_adaptador(self):
        cfg = carregar_config_observation_affective(ATLAS / "config_observation_affective.json")
        self.assertEqual(1024, cfg.capacidade_stimulus_ids)
        self.assertEqual(128, cfg.capacidade_incidentes)
        self.assertEqual(32, cfg.capacidade_assuntos)
        self.assertEqual(64, cfg.capacidade_erros)
        self.assertEqual(86400.0, cfg.janela_reincidencia_s)
        self.assertEqual(3, cfg.limite_repeticoes)
        self.assertEqual(1.0, cfg.impacto.gravidades["critical"])

    def test_foundation_ci_expoe_gate_dedicado(self):
        workflow = (ROOT / ".github" / "workflows" / "foundation-ci.yml").read_text(encoding="utf-8")
        for nome in (
            "adaptador_impacto_afetivo.py",
            "pipeline_afetivo_observacional.py",
            "config_observation_affective.json",
            "DEVEX_HOMELAB_ATLAS_OBSERVATION_AFFECTIVE_PIPELINE_PASS",
        ):
            self.assertIn(nome, workflow)


if __name__ == "__main__":
    unittest.main()
