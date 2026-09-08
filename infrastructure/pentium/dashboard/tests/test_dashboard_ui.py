import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DashboardUiContractTests(unittest.TestCase):
    def test_ui_contains_pipeline_and_two_second_polling(self):
        html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
        for label in ("MIC", "ANC", "VAD", "Whisper", "Wake", "Qwen", "TTS"):
            self.assertIn(label, html)
        self.assertIn("setInterval(refreshAll, 2000)", html)

    def test_ui_has_no_control_actions(self):
        html = (ROOT / "dashboard.html").read_text(encoding="utf-8").lower()
        for forbidden in ("restart", "reboot", "shutdown", "managedcontrolservice", "fetch('/api/control"):
            self.assertNotIn(forbidden, html)

    def test_ui_preserves_portuguese_copy_without_mojibake(self):
        html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
        for corrupted in ("Presen?a", "Express?o", "intera??o", "Servi?os", "?udio", "t?cnica"):
            self.assertNotIn(corrupted, html)
        self.assertIn("Presen&ccedil;a cognitiva", html)

    def test_ui_renders_cognitive_avatar_from_visual_contract(self):
        html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
        for token in ("atlasAvatar", "avatarMode", "avatarExpression", "avatarFocus", "status.visual", "data-mode", "data-expression"):
            self.assertIn(token, html)
        self.assertIn("<svg", html)
        self.assertIn("viewBox", html)

    def test_avatar_renderer_is_externalized_behind_stable_boundary(self):
        html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
        renderer = (ROOT / "atlas-avatar-renderer.js").read_text(encoding="utf-8")
        self.assertIn('src="/assets/atlas-avatar-renderer.js"', html)
        self.assertIn("AtlasAvatarRenderer.render(status.visual)", html)
        self.assertNotIn("function renderAvatar", html)
        self.assertIn("window.AtlasAvatarRenderer", renderer)
        self.assertIn("function render(visual)", renderer)


if __name__ == "__main__":
    unittest.main()
