import unittest
from pathlib import Path

from infrastructure.pentium.atlas.configuracao_cognitiva import (
    PoliticaContextoCognitivo,
    carregar_configuracao_cognitiva,
)

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"


class ConfiguracaoCognitivaTests(unittest.TestCase):
    def test_configuracao_carrega_bounds_aprovados(self):
        cfg = carregar_configuracao_cognitiva(ATLAS / "config_cognitiva.json")
        self.assertEqual(1, cfg.schema_version)
        self.assertEqual(256, cfg.contexto.max_string_chars)
        self.assertEqual(8, cfg.contexto.max_mudancas_recentes)
        self.assertEqual(8192, cfg.contexto.max_payload_bytes)
        self.assertEqual(4, cfg.ativacao.max_ativacoes_autonomas_janela)

    def test_configuracao_rejeita_limites_invalidos(self):
        with self.assertRaises(ValueError):
            PoliticaContextoCognitivo(0, 8, 8, 2, 8192)


if __name__ == "__main__":
    unittest.main()
