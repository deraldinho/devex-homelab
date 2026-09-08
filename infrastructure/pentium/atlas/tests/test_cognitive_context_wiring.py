import inspect
import unittest

from infrastructure.pentium.atlas import chat_cli, voice_daemon


class CognitiveContextWiringTest(unittest.TestCase):
    def test_cli_wires_observation_bridge_policy_and_expected_sha(self):
        source = inspect.getsource(chat_cli._build_gateway)
        self.assertIn("observation_bridge.snapshot_path", source)
        self.assertIn("max_snapshot_age_s", source)
        self.assertIn("ATLAS_EXPECTED_SHA", source)

    def test_voice_wires_same_read_only_observation_context_without_enabling_audio(self):
        source = inspect.getsource(voice_daemon.build_runtime)
        self.assertIn("observation_bridge.snapshot_path", source)
        self.assertIn("max_snapshot_age_s", source)
        self.assertIn("ATLAS_EXPECTED_SHA", source)
        self.assertNotIn("systemctl", source)


if __name__ == "__main__":
    unittest.main()
