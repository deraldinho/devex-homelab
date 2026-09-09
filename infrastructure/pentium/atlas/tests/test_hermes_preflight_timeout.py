import subprocess
import unittest
from infrastructure.pentium.atlas.config_hermes import HermesConfig
from infrastructure.pentium.atlas.hermes_preflight import HermesPreflight

class HermesPreflightTimeoutTests(unittest.TestCase):
    def test_offline_preflight_allows_slow_pentium_startup(self):
        seen = []
        cfg = HermesConfig(1, "openai-codex", "atlas", "hermes", 45.0, 4096, 16384)
        def runner(command, **kwargs):
            seen.append((command, kwargs["timeout"]))
            if command[1:3] == ["profile", "show"]:
                return subprocess.CompletedProcess(command, 0, "Profile: atlas\n", "")
            return subprocess.CompletedProcess(command, 0, '{"tools":{"count":0}}', "")
        result = HermesPreflight(cfg, runner=runner).check()
        self.assertTrue(result.ok)
        self.assertGreaterEqual(seen[1][1], 20.0)

if __name__ == "__main__":
    unittest.main()
