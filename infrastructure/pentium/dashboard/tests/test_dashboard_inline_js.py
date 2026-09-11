import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DashboardInlineJsTests(unittest.TestCase):
    def test_inline_dashboard_script_is_valid_javascript(self):
        html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
        scripts = re.findall(r"<script(?: [^>]*)?>(.*?)</script>", html, re.S)
        self.assertTrue(scripts)
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as handle:
            handle.write(scripts[-1])
            path = handle.name
        result = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
