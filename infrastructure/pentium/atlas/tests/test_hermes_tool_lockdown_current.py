import subprocess
import unittest
from pathlib import Path
from infrastructure.pentium.atlas.config_hermes import HermesConfig
from infrastructure.pentium.atlas.hermes_preflight import HermesPreflight

ROOT = Path(__file__).resolve().parents[1]

class HermesCurrentToolLockdownTests(unittest.TestCase):
    def cfg(self):
        return HermesConfig(1, "openai-codex", "atlas", "hermes", 45.0, 4096, 16384)

    def test_preflight_uses_offline_json_tool_count(self):
        calls = []
        def runner(command, **kwargs):
            calls.append(command)
            if command[1:3] == ["profile", "show"]:
                return subprocess.CompletedProcess(command, 0, "Profile: atlas\n", "")
            return subprocess.CompletedProcess(command, 0, '{"tools":{"count":0}}\n', "")
        result = HermesPreflight(self.cfg(), runner=runner).check()
        self.assertTrue(result.ok)
        self.assertIn("--json", calls[1])

    def test_provisioner_disables_current_builtin_toolsets(self):
        text = (ROOT / "prepare-hermes-atlas.sh").read_text(encoding="utf-8")
        self.assertIn("connections", text)
        self.assertIn("computer_use", text)

if __name__ == "__main__":
    unittest.main()
