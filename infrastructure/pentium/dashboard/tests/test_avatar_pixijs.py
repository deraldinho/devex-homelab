import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AvatarPixiContractTests(unittest.TestCase):
    def test_renderer_normalizes_visual_contract(self):
        renderer = (ROOT / "atlas-avatar-renderer.js").read_text(encoding="utf-8")
        for token in ("normalize", "clamp01", "clampMs", "transicao_ms", "direcao_olhar", "gesto_atual"):
            self.assertIn(token, renderer)
        self.assertIn("Math.max(120, Math.min(1500", renderer)

    def test_pixijs_engine_is_full_body_and_fallback_safe(self):
        engine = (ROOT / "atlas-avatar-engine.js").read_text(encoding="utf-8")
        for token in ("new PIXI.Application", "#buildRig", "armL", "armR", "head", "hairBack", "mouth", "eyeL", "eyeR"):
            self.assertIn(token, engine)
        self.assertIn("return false", engine)
        self.assertIn("prefers-reduced-motion", engine)
        self.assertIn("visibilitychange", engine)

    def test_engine_supports_all_modes_and_archetypes(self):
        engine = (ROOT / "atlas-avatar-engine.js").read_text(encoding="utf-8")
        for mode in ("OCIOSO", "OBSERVANDO", "CONVERSANDO", "REAGINDO"):
            self.assertIn(mode, engine)
        for expression in ("SERENO", "ENGAJADO", "CURIOSO", "ATENTO", "PREOCUPADO", "SOB_PRESSAO", "RECUPERANDO"):
            self.assertIn(expression, engine)
        self.assertIn("minArchetypeDwellMs: 1200", engine)

    def test_fetch_script_pins_release_and_sha(self):
        script = (ROOT / "fetch-pixi.sh").read_text(encoding="utf-8")
        self.assertIn('VERSION="8.20.1"', script)
        self.assertIn("9948591083793305468d73915a3ea85032dcf8e32eee7a1328585050d7a14d53", script)
        self.assertIn("sha256sum --check --status", script)
        self.assertIn("github.com/pixijs/pixijs/releases/download", script)

    def test_javascript_assets_are_syntax_valid(self):
        for name in ("atlas-avatar-engine.js", "atlas-avatar-renderer.js"):
            result = subprocess.run(["node", "--check", str(ROOT / name)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
