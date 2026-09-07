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


if __name__ == "__main__":
    unittest.main()
