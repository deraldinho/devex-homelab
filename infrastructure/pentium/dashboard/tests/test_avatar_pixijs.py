import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AvatarPixiContractTests(unittest.TestCase):
    def test_renderer_normalizes_visual_contract(self):
        renderer = (ROOT / "atlas-avatar-renderer.js").read_text(encoding="utf-8")
        for token in ("normalize", "transicao_ms", "velocidade_movimento", "intensidade_movimento"):
            self.assertIn(token, renderer)

    def test_pixijs_engine_is_local_and_full_body(self):
        html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
        engine = (ROOT / "atlas-avatar-engine.js").read_text(encoding="utf-8")
        self.assertIn('/assets/pixi.min.js', html)
        self.assertIn('/assets/atlas-avatar-engine.js', html)
        self.assertIn('id="atlasPixiStage"', html)
        for token in ("PIXI.Application", "leftArm", "rightArm", "leftEye", "rightEye", "mouth", "torso"):
            self.assertIn(token, engine)

    def test_engine_supports_all_modes_archetypes_and_motion_policy(self):
        engine = (ROOT / "atlas-avatar-engine.js").read_text(encoding="utf-8")
        for token in ("OCIOSO", "OBSERVANDO", "CONVERSANDO", "REAGINDO"):
            self.assertIn(token, engine)
        for token in ("SERENO", "ENGAJADO", "CURIOSO", "ATENTO", "PREOCUPADO", "SOB_PRESSAO", "RECUPERANDO"):
            self.assertIn(token, engine)
        for token in ("prefers-reduced-motion", "visibilitychange", "gesto_atual", "direcao_olhar"):
            self.assertIn(token, engine)

    def test_javascript_assets_are_syntax_valid(self):
        for name in ("atlas-avatar-renderer.js", "atlas-avatar-engine.js"):
            result = subprocess.run(["node", "--check", str(ROOT / name)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
