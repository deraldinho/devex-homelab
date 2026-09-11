import subprocess
import unittest

from infrastructure.pentium.atlas.config_hermes import HermesConfig
from infrastructure.pentium.atlas.hermes_preflight import HermesPreflight


class HermesPreflightTests(unittest.TestCase):
    def cfg(self):
        return HermesConfig(1, "openai-codex", "atlas", "hermes", 45.0, 4096, 16384)

    def test_accepts_existing_profile_with_zero_cli_tools(self):
        calls = []
        def runner(command, **kwargs):
            calls.append(command)
            if command[1:3] == ["profile", "show"]:
                return subprocess.CompletedProcess(command, 0, "Profile: atlas\n", "")
            return subprocess.CompletedProcess(command, 0, "Tool schemas : 2 B (0 tools)\n", "")
        result = HermesPreflight(self.cfg(), runner=runner).check()
        self.assertTrue(result.ok)
        self.assertEqual(0, result.tool_count)
        self.assertEqual(["hermes", "profile", "show", "atlas"], calls[0])

    def test_rejects_profile_with_any_enabled_tool(self):
        def runner(command, **kwargs):
            if command[1:3] == ["profile", "show"]:
                return subprocess.CompletedProcess(command, 0, "Profile: atlas\n", "")
            return subprocess.CompletedProcess(command, 0, "Tool schemas : 4.2 KB (27 tools)\n", "")
        result = HermesPreflight(self.cfg(), runner=runner).check()
        self.assertFalse(result.ok)
        self.assertEqual(27, result.tool_count)
        self.assertEqual("tools_enabled", result.reason)

    def test_rejects_missing_profile_and_does_not_leak_stderr(self):
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, "", "token=secret")
        result = HermesPreflight(self.cfg(), runner=runner).check()
        self.assertFalse(result.ok)
        self.assertEqual("profile_unavailable", result.reason)
        self.assertNotIn("secret", repr(result))


if __name__ == "__main__":
    unittest.main()
