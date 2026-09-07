import unittest
from pathlib import Path

from infrastructure.pentium.atlas.configuracao_llm import (
    ConfiguracaoLlm,
    carregar_configuracao_llm,
)

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"


class ConfiguracaoLlmTests(unittest.TestCase):
    def test_configuracao_carrega_backend_local_e_bounds(self):
        cfg = carregar_configuracao_llm(ATLAS / "config_llm.json")
        self.assertEqual(1, cfg.schema_version)
        self.assertEqual("llama_cpp", cfg.backend)
        self.assertEqual("Qwen3-0.6B", cfg.modelo_nome)
        self.assertGreater(cfg.timeout_s, 0)
        self.assertGreater(cfg.max_saida_bytes, 0)

    def test_configuracao_rejeita_backend_desconhecido(self):
        with self.assertRaises(ValueError):
            ConfiguracaoLlm(1, "remote_api", "x", "modelo.gguf", 5.0, 2048, 4096)


if __name__ == "__main__":
    unittest.main()
