import unittest
from pathlib import Path

from infrastructure.pentium.atlas.config_llama_server import carregar_configuracao_llama_server


class ConfigLlamaServerTests(unittest.TestCase):
    def test_config_repo_declara_bounds_e_nao_persiste_kv(self):
        path = Path(__file__).resolve().parents[1] / 'config_llama_server.json'
        cfg = carregar_configuracao_llama_server(path)
        self.assertEqual('/run/user/1000/atlas-llm.sock', cfg.socket_path)
        self.assertEqual(4096, cfg.context_size)
        self.assertEqual(64, cfg.cache_reuse)
        self.assertEqual(8192, cfg.max_response_bytes)
        self.assertFalse(cfg.persist_kv_cache)
