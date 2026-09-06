import unittest

from infrastructure.pentium.atlas.modelo_fast_dispatch import (
    EstadoLaneDispatch,
    ResultadoFastDispatch,
    ResultadoLaneDispatch,
)
from infrastructure.pentium.atlas.modelo_fast_router import RotaSemantica


class ModeloFastDispatchTests(unittest.TestCase):
    def test_preserva_ordem_e_classifica_resultados(self):
        resultado = ResultadoFastDispatch(
            solicitadas=(RotaSemantica.FAST_REACTION, RotaSemantica.AFFECT, RotaSemantica.SLOW_LLM),
            resultados=(
                ResultadoLaneDispatch(RotaSemantica.FAST_REACTION, EstadoLaneDispatch.DELIVERED, "reaction:ok"),
                ResultadoLaneDispatch(RotaSemantica.AFFECT, EstadoLaneDispatch.FAILED, "affect:error"),
                ResultadoLaneDispatch(RotaSemantica.SLOW_LLM, EstadoLaneDispatch.DEFERRED, "slow:queued"),
            ),
        )
        self.assertEqual(resultado.entregues, (RotaSemantica.FAST_REACTION,))
        self.assertEqual(resultado.falhas, (RotaSemantica.AFFECT,))
        self.assertEqual(resultado.deferidas, (RotaSemantica.SLOW_LLM,))
    def test_drop_deve_ser_exclusivo(self):
        with self.assertRaises(ValueError):
            ResultadoFastDispatch(
                solicitadas=(RotaSemantica.DROP, RotaSemantica.AFFECT),
                resultados=(),
            )

    def test_resultado_deve_corresponder_a_rota_solicitada(self):
        with self.assertRaises(ValueError):
            ResultadoFastDispatch(
                solicitadas=(RotaSemantica.AFFECT,),
                resultados=(
                    ResultadoLaneDispatch(RotaSemantica.FAST_REACTION, EstadoLaneDispatch.DELIVERED, "ok"),
                ),
            )

    def test_detalhe_deve_ser_bounded_e_nao_vazio(self):
        with self.assertRaises(ValueError):
            ResultadoLaneDispatch(RotaSemantica.AFFECT, EstadoLaneDispatch.DELIVERED, "")
        with self.assertRaises(ValueError):
            ResultadoLaneDispatch(RotaSemantica.AFFECT, EstadoLaneDispatch.DELIVERED, "x" * 129)


if __name__ == "__main__":
    unittest.main()
