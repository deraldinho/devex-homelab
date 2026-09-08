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

if __name__ == "__main__":
    unittest.main()

class DashboardCognitivePanelUiTests(unittest.TestCase):
    def test_ui_contains_mind_panel_contract(self):
        html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
        for token in ("Mente do Atlas", "cognitionStatus", "cognitionPipeline", "a1Metrics", "a3Perception", "a4Emotion", "cognitionChanges", "renderCognition", "status.cognition"):
            self.assertIn(token, html)

    def test_ui_contains_cognition_states_without_controls(self):
        html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
        for token in ("available", "stale", "unavailable", "CONTEXTO INDISPONÍVEL"):
            self.assertIn(token, html)
        self.assertNotIn("/api/cognition/control", html)
