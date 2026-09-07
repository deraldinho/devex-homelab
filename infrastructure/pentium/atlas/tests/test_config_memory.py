import unittest
from pathlib import Path

from infrastructure.pentium.atlas.config_memory import load_memory_config


class MemoryConfigTests(unittest.TestCase):
    def test_config_repo_declara_bounds_e_thresholds(self):
        path = Path("infrastructure/pentium/atlas/config_memory.json")
        cfg = load_memory_config(path)
        self.assertEqual(10000, cfg.max_records)
        self.assertEqual(8 * 1024 * 1024, cfg.max_bytes)
        self.assertEqual((0.70, 0.85, 0.95), (
            cfg.cleanup_ratio, cfg.consolidate_ratio, cfg.evict_ratio,
        ))
        self.assertEqual(6, cfg.retriever_max_items)
        self.assertEqual(2048, cfg.retriever_max_bytes)


if __name__ == "__main__":
    unittest.main()
