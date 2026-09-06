from dataclasses import FrozenInstanceError
import unittest

from infrastructure.pentium.atlas.modelo_fast_router import (
    DecisaoFastRouter,
    RotaSemantica,
)


class ModeloFastRouterTests(unittest.TestCase):
    def test_decisao_multilane_e_imutavel(self):
        decisao = DecisaoFastRouter(
            rotas=(RotaSemantica.FAST_REACTION, RotaSemantica.AFFECT),
            motivo="critico_direto",
            score=1.0,
        )
        self.assertEqual(
            decisao.to_dict()["rotas"],
            ["fast_reaction", "affect"],
        )
        with self.assertRaises(FrozenInstanceError):
            decisao.score = 0.0

    def test_drop_e_exclusivo(self):
        with self.assertRaises(ValueError):
            DecisaoFastRouter(
                rotas=(RotaSemantica.DROP, RotaSemantica.AFFECT),
                motivo="invalido",
                score=0.1,
            )
    def test_decisao_rejeita_rotas_vazias_duplicadas_score_e_motivo_invalidos(self):
        casos = (
            {"rotas": (), "motivo": "x", "score": 0.2},
            {"rotas": (RotaSemantica.AFFECT, RotaSemantica.AFFECT), "motivo": "x", "score": 0.2},
            {"rotas": (RotaSemantica.AFFECT,), "motivo": "", "score": 0.2},
            {"rotas": (RotaSemantica.AFFECT,), "motivo": "x", "score": -0.1},
            {"rotas": (RotaSemantica.AFFECT,), "motivo": "x", "score": 1.1},
        )
        for caso in casos:
            with self.subTest(caso=caso):
                with self.assertRaises(ValueError):
                    DecisaoFastRouter(**caso)

    def test_rotas_canonicas_sao_estaveis(self):
        self.assertEqual(
            [rota.value for rota in RotaSemantica],
            ["drop", "fast_reaction", "affect", "cache_lookup", "slow_llm"],
        )


if __name__ == "__main__":
    unittest.main()
