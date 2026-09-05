import unittest
from pathlib import Path

from infrastructure.pentium.atlas.config_cache import load_cache_config


class CacheConfigTests(unittest.TestCase):
    def test_config_repo_declara_policy_k1(self):
        path = Path("infrastructure/pentium/atlas/config_cache.json")
        config = load_cache_config(path)
        self.assertEqual(64, config.max_entries)
        self.assertEqual(300.0, config.ttl_s)
        self.assertEqual("Qwen3-0.6B-Q4", config.model_id)
        self.assertEqual("k1-v1", config.policy_version)


if __name__ == "__main__":
    unittest.main()