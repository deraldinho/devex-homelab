import unittest
from pathlib import Path

from infrastructure.pentium.atlas.configuracao_cognitiva import carregar_configuracao_cognitiva

ATLAS = Path(__file__).resolve().parents[1]


class ConfiguracaoCognitivaObservationBridgeTest(unittest.TestCase):
    def test_config_exposes_observation_bridge_policy(self):
        cfg = carregar_configuracao_cognitiva(ATLAS / "config_cognitiva.json")
        self.assertEqual("~/pentium-agent/atlas/runtime/cognitive-observation-context.json",
                         cfg.observation_bridge.snapshot_path)
        self.assertEqual(180, cfg.observation_bridge.max_snapshot_age_s)
        self.assertTrue(cfg.observation_bridge.require_expected_sha)


if __name__ == "__main__":
    unittest.main()
