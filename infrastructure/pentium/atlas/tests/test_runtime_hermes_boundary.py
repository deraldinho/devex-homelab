import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RuntimeHermesBoundaryTests(unittest.TestCase):
    def test_cli_and_voice_use_shared_hermes_backend(self):
        for name in ("chat_cli.py", "voice_daemon.py"):
            source = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("HermesAdapter", source)
            self.assertIn("load_hermes_config", source)
            self.assertNotIn("LlamaCppBackend", source)
            self.assertNotIn("runtime_root / \"llama", source)

    def test_voice_config_has_no_llm_or_qwen_fields(self):
        payload = json.loads((ROOT / "config_voice.json").read_text(encoding="utf-8"))
        for key in ("llm_model", "llm_timeout_s", "llm_context_tokens"):
            self.assertNotIn(key, payload)
        self.assertNotIn("Qwen", json.dumps(payload))

    def test_cache_identity_is_hermes_codex(self):
        payload = json.loads((ROOT / "config_cache.json").read_text(encoding="utf-8"))
        self.assertEqual("hermes/openai-codex", payload["model_id"])
