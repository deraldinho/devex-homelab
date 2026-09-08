import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"

class AffectiveRuntimePackagingTests(unittest.TestCase):
    def test_installer_empacota_runtime_visual_e_config(self):
        texto = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        for nome in (
            "modelo_visual_atlas.py", "compositor_visual_afetivo.py",
            "visual_state_publisher.py", "affective_runtime.py",
            "config_affective_runtime.json", "ATLAS_AFFECTIVE_RUNTIME_INSTALL_PASS",
        ):
            self.assertIn(nome, texto)

    def test_config_runtime_e_versionada_e_bounded(self):
        cfg = json.loads((ATLAS / "config_affective_runtime.json").read_text(encoding="utf-8"))
        self.assertEqual(1, cfg["schema_version"])
        self.assertEqual("~/pentium-agent/atlas/runtime/visual-state.json", cfg["visual_state_path"])
        self.assertGreaterEqual(cfg["tick_interval_ms"], 100)
        self.assertLessEqual(cfg["tick_interval_ms"], 5000)
        self.assertGreaterEqual(cfg["visual_heartbeat_s"], 5)
        self.assertLessEqual(cfg["visual_heartbeat_s"], 300)

    def test_foundation_ci_expoe_gate_dedicado(self):
        workflow = (ROOT / ".github" / "workflows" / "foundation-ci.yml").read_text(encoding="utf-8")
        self.assertIn("DEVEX_HOMELAB_ATLAS_AFFECTIVE_RUNTIME_PASS", workflow)
        self.assertIn("config_affective_runtime.json", workflow)
        self.assertIn("affective_runtime.py", workflow)

if __name__ == "__main__":
    unittest.main()
