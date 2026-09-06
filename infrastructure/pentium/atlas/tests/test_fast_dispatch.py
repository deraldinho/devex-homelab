import unittest

from infrastructure.pentium.atlas.fast_dispatch import FastDispatcher
from infrastructure.pentium.atlas.modelo_evento_semantico import (
    EntidadeSemantica, EstadoSemantico, EventoSemantico, TipoEventoSemantico,
)
from infrastructure.pentium.atlas.modelo_fast_dispatch import EstadoLaneDispatch
from infrastructure.pentium.atlas.modelo_fast_router import DecisaoFastRouter, RotaSemantica
from infrastructure.pentium.atlas.stimulus_model import StimulusSeverity


def evento():
    return EventoSemantico(
        entity=EntidadeSemantica.CORE,
        event=TipoEventoSemantico.STATE_CHANGED,
        state=EstadoSemantico.DEGRADED,
        severity=StimulusSeverity.WARNING,
        novelty=0.7,
        correlation_id="corr-s3",
        attributes={},
    )


class Porta:
    def __init__(self, nome, chamadas, *, falhar=False):
        self.nome = nome
        self.chamadas = chamadas
        self.falhar = falhar

    def _run(self, evento_semantico):
        self.chamadas.append(self.nome)
        if self.falhar:
            raise RuntimeError("falha de teste")
        return f"{self.nome}:ok"

    def reagir(self, evento_semantico):
        return self._run(evento_semantico)

    def aplicar(self, evento_semantico):
        return self._run(evento_semantico)

    def consultar(self, evento_semantico):
        return self._run(evento_semantico)

    def defer(self, evento_semantico):
        return self._run(evento_semantico)


class FastDispatcherTests(unittest.TestCase):
    def test_drop_nao_chama_portas(self):
        chamadas = []
        porta = Porta("reaction", chamadas)
        dispatcher = FastDispatcher(fast_reaction=porta, affect=porta, cache_lookup=porta, slow_llm=porta)
        resultado = dispatcher.dispatch(evento(), DecisaoFastRouter((RotaSemantica.DROP,), "drop", 0.1))
        self.assertEqual(chamadas, [])
        self.assertEqual(resultado.resultados, ())
    def test_preserva_ordem_e_entrega_fast_reaction_e_affect(self):
        chamadas = []
        dispatcher = FastDispatcher(
            fast_reaction=Porta("reaction", chamadas),
            affect=Porta("affect", chamadas),
        )
        decisao = DecisaoFastRouter(
            (RotaSemantica.FAST_REACTION, RotaSemantica.AFFECT),
            "critico_direto",
            1.0,
        )
        resultado = dispatcher.dispatch(evento(), decisao)
        self.assertEqual(chamadas, ["reaction", "affect"])
        self.assertEqual(resultado.entregues, decisao.rotas)

    def test_falha_de_lane_nao_bloqueia_lane_seguinte(self):
        chamadas = []
        dispatcher = FastDispatcher(
            fast_reaction=Porta("reaction", chamadas, falhar=True),
            affect=Porta("affect", chamadas),
        )
        decisao = DecisaoFastRouter(
            (RotaSemantica.FAST_REACTION, RotaSemantica.AFFECT),
            "critico_direto",
            1.0,
        )
        resultado = dispatcher.dispatch(evento(), decisao)
        self.assertEqual(chamadas, ["reaction", "affect"])
        self.assertEqual(resultado.falhas, (RotaSemantica.FAST_REACTION,))
        self.assertEqual(resultado.entregues, (RotaSemantica.AFFECT,))
    def test_cache_lookup_e_delegado(self):
        chamadas = []
        dispatcher = FastDispatcher(cache_lookup=Porta("cache", chamadas))
        decisao = DecisaoFastRouter((RotaSemantica.CACHE_LOOKUP,), "cache", 0.4)
        resultado = dispatcher.dispatch(evento(), decisao)
        self.assertEqual(chamadas, ["cache"])
        self.assertEqual(resultado.entregues, (RotaSemantica.CACHE_LOOKUP,))

    def test_slow_llm_e_deferido_sem_inferencia_inline(self):
        chamadas = []
        dispatcher = FastDispatcher(slow_llm=Porta("slow", chamadas))
        decisao = DecisaoFastRouter((RotaSemantica.SLOW_LLM,), "slow", 0.4)
        resultado = dispatcher.dispatch(evento(), decisao)
        self.assertEqual(chamadas, ["slow"])
        self.assertEqual(resultado.deferidas, (RotaSemantica.SLOW_LLM,))
        self.assertEqual(resultado.resultados[0].estado, EstadoLaneDispatch.DEFERRED)


if __name__ == "__main__":
    unittest.main()
