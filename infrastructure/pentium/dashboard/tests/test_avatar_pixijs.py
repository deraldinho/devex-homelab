import json
import subprocess
import textwrap
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
        for token in ("new PIXI.Application", "#buildRig", "armL", "armR", "legL", "legR", "head", "hairBack", "mouth", "eyeL", "eyeR"):
            self.assertIn(token, engine)
        self.assertIn("return false", engine)
        self.assertIn("prefers-reduced-motion", engine)
        self.assertIn("visibilitychange", engine)

    def test_engine_supports_all_modes_archetypes_and_gestures(self):
        engine = (ROOT / "atlas-avatar-engine.js").read_text(encoding="utf-8")
        for mode in ("OCIOSO", "OBSERVANDO", "CONVERSANDO", "REAGINDO"):
            self.assertIn(mode, engine)
        for expression in ("SERENO", "ENGAJADO", "CURIOSO", "ATENTO", "PREOCUPADO", "SOB_PRESSAO", "RECUPERANDO"):
            self.assertIn(expression, engine)
        for gesture in ("ACENO", "DUVIDA", "ESCUTA", "ABERTO", "FECHADO", "SURPRESA", "ALIVIO"):
            self.assertIn(gesture, engine)
        self.assertIn("minArchetypeDwellMs: 1200", engine)

    def test_hysteresis_holds_normal_archetype_and_allows_critical_bypass(self):
        renderer_path = json.dumps(str(ROOT / "atlas-avatar-renderer.js"))
        script = textwrap.dedent(f"""
            global.window = {{}};
            global.document = {{ getElementById: () => null }};
            global.performance = {{ now: () => 0 }};
            require({renderer_path});
            const r = window.AtlasAvatarRenderer;
            r.resetTransitionState();
            const base = r.normalize({{ modo: 'OCIOSO', expressao: 'SERENO', foco_visual: 'x99' }});
            const first = r.settleVisualState(base, 0);
            const early = r.settleVisualState(r.normalize({{ modo: 'OBSERVANDO', expressao: 'CURIOSO', foco_visual: 'core', direcao_olhar: 'direita' }}), 500);
            const late = r.settleVisualState(r.normalize({{ modo: 'OBSERVANDO', expressao: 'CURIOSO', foco_visual: 'core' }}), 1300);
            const critical = r.settleVisualState(r.normalize({{ modo: 'REAGINDO', expressao: 'SOB_PRESSAO', foco_visual: 'core' }}), 1400);
            console.log(JSON.stringify({{ first, early, late, critical }}));
        """)
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["early"]["expressao"], "SERENO")
        self.assertEqual(payload["early"]["foco_visual"], "core")
        self.assertEqual(payload["early"]["direcao_olhar"], "direita")
        self.assertEqual(payload["late"]["expressao"], "CURIOSO")
        self.assertEqual(payload["critical"]["expressao"], "SOB_PRESSAO")

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
