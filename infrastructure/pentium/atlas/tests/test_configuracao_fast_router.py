import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from infrastructure.pentium.atlas.configuracao_fast_router import (
    PoliticaFastRouter,
    carregar_politica_fast_router,
)


ROOT = Path(__file__).resolve().parents[1]


class ConfiguracaoFastRouterTests(unittest.TestCase):
    def test_config_repo_declara_thresholds_coerentes(self):
        politica = carregar_politica_fast_router(ROOT / "config_fast_router.json")
        self.assertEqual(politica.drop_score_max, 0.15)
        self.assertEqual(politica.cache_novelty_max, 0.25)
        self.assertEqual(politica.fast_reaction_score_min, 0.70)
        self.assertEqual(politica.slow_llm_score_min, 0.40)
        self.assertEqual(politica.slow_llm_score_max, 0.69)
        self.assertEqual(politica.slow_llm_novelty_min, 0.80)

    def test_politica_rejeita_thresholds_sobrepostos_ou_fora_de_bound(self):
        base = dict(
            drop_score_max=0.15,
            cache_novelty_max=0.25,
            fast_reaction_score_min=0.70,
            slow_llm_score_min=0.40,
            slow_llm_score_max=0.69,
            slow_llm_novelty_min=0.80,
        )
        casos = (
            {**base, "drop_score_max": -0.1},
            {**base, "cache_novelty_max": 1.1},
            {**base, "drop_score_max": 0.45},
            {**base, "slow_llm_score_max": 0.75},
            {**base, "slow_llm_novelty_min": 1.1},
        )
        for caso in casos:
            with self.subTest(caso=caso):
                with self.assertRaises(ValueError):
                    PoliticaFastRouter(**caso)

    def test_loader_rejeita_schema_incompativel(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "config.json"
            path.write_text(json.dumps({"schema_version": 2}), encoding="utf-8")
            with self.assertRaises(ValueError):
                carregar_politica_fast_router(path)


if __name__ == "__main__":
    unittest.main()
