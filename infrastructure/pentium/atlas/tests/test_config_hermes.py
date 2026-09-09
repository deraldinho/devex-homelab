import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.config_hermes import HermesConfig, load_hermes_config

ROOT = Path(__file__).resolve().parents[1]


class HermesConfigTests(unittest.TestCase):
    def test_repository_config_is_bounded_and_codex_only(self):
        cfg = load_hermes_config(ROOT / "config_hermes.json")
        self.assertEqual(1, cfg.schema_version)
        self.assertEqual("openai-codex", cfg.provider)
        self.assertEqual("atlas", cfg.profile)
        self.assertGreater(cfg.timeout_s, 0)
        self.assertGreater(cfg.max_response_bytes, 0)

    def test_rejects_non_codex_provider(self):
        with self.assertRaises(ValueError):
            HermesConfig(1, "openrouter", "atlas", "hermes", 30.0, 4096, 16384)

    def test_loader_does_not_require_or_accept_secret_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hermes.json"
            path.write_text(json.dumps({
                "schema_version": 1, "provider": "openai-codex", "profile": "atlas",
                "binary": "hermes", "timeout_s": 30.0, "max_response_bytes": 16384,
                "oauth_token": "must-not-be-here"
            }), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_hermes_config(path)


if __name__ == "__main__":
    unittest.main()
