import unittest

from infrastructure.pentium.atlas.modelo_contexto_cognitivo import DecisaoAtivacaoCognitiva, MotivoAtivacaoCognitiva
from infrastructure.pentium.atlas.modelo_llm_gateway import ErroInferencia, ResultadoInferencia
from infrastructure.pentium.atlas.reaction_loop_cognitivo import ReactionLoopCognitivo


class FakePolicy:
    def __init__(self, decisao):
        self.decisao = decisao
        self.registros = []

    def avaliar(self, **kwargs):
        self.avaliado = kwargs
        return self.decisao

    def registrar_ativacao(self, fingerprint, agora, autonomo):
        self.registros.append((fingerprint, agora, autonomo))


class FakeBuilder:
    def construir(self, **kwargs):
        self.kwargs = kwargs
        return object()


class FakeGateway:
    def __init__(self, resultado):
        self.resultado = resultado
        self.calls = []

    def inferir(self, contexto, tarefa):
        self.calls.append((contexto, tarefa))
        return self.resultado


class ReactionLoopCognitivoTests(unittest.TestCase):
    def test_sem_ativacao_nao_constroi_contexto_nem_chama_gateway(self):
        policy = FakePolicy(DecisaoAtivacaoCognitiva(False, None, "cooldown"))
        builder = FakeBuilder()
        gateway = FakeGateway(ResultadoInferencia(True, "x", None, 1, "fake"))
        loop = ReactionLoopCognitivo(policy, builder, gateway)

        resposta = loop.processar(
            fingerprint="fp-1", agora="2026-09-05T20:10:00+00:00",
            sinais_ativacao={}, dados_contexto={}
        )
        self.assertFalse(resposta.ativado)
        self.assertEqual("cooldown", resposta.razao)
        self.assertEqual([], gateway.calls)
        self.assertFalse(hasattr(builder, "kwargs"))

    def test_ativacao_chama_builder_gateway_e_registra_autonomo(self):
        policy = FakePolicy(DecisaoAtivacaoCognitiva(True, MotivoAtivacaoCognitiva.NOVIDADE_RELEVANTE))
        builder = FakeBuilder()
        gateway = FakeGateway(ResultadoInferencia(True, "O Core mudou.", None, 12, "fake"))
        loop = ReactionLoopCognitivo(policy, builder, gateway)

        resposta = loop.processar(
            fingerprint="fp-2", agora="2026-09-05T20:11:00+00:00",
            sinais_ativacao={"novidade": 0.9}, dados_contexto={"assessment": object()}
        )
        self.assertTrue(resposta.ativado)
        self.assertEqual("O Core mudou.", resposta.texto)
        self.assertEqual("novidade_relevante", resposta.motivo)
        self.assertEqual(1, len(gateway.calls))
        self.assertEqual([("fp-2", "2026-09-05T20:11:00+00:00", True)], policy.registros)

    def test_falha_llm_vira_fallback_estruturado_sem_excecao(self):
        policy = FakePolicy(DecisaoAtivacaoCognitiva(True, MotivoAtivacaoCognitiva.INTERACAO_HUMANA))
        builder = FakeBuilder()
        gateway = FakeGateway(ResultadoInferencia(False, None, ErroInferencia.TIMEOUT, 5000, "fake"))
        loop = ReactionLoopCognitivo(policy, builder, gateway)
        resposta = loop.processar(
            fingerprint="fp-3", agora="2026-09-05T20:12:00+00:00",
            sinais_ativacao={"interacao_humana": True}, dados_contexto={}
        )
        self.assertTrue(resposta.ativado)
        self.assertEqual("cognitive_backend_unavailable", resposta.razao)
        self.assertIsNone(resposta.texto)
        self.assertEqual([("fp-3", "2026-09-05T20:12:00+00:00", False)], policy.registros)


if __name__ == "__main__":
    unittest.main()


class FakeRetriever:
    def __init__(self, result=(), error=None):
        self.result = result
        self.error = error
        self.calls = []

    def retrieve(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.result


class _Percepcao:
    entidade_id = "core"


class ReactionLoopMemoryTests(unittest.TestCase):
    def test_retriever_alimenta_builder_sem_expor_store_ao_gateway(self):
        policy = FakePolicy(DecisaoAtivacaoCognitiva(True, MotivoAtivacaoCognitiva.INTERACAO_HUMANA))
        builder = FakeBuilder()
        gateway = FakeGateway(ResultadoInferencia(True, "ok", None, 2, "fake"))
        retriever = FakeRetriever(({"memory_id": "m1", "content": "Core e membro"},))
        loop = ReactionLoopCognitivo(policy, builder, gateway, memory_retriever=retriever)
        loop.processar(
            fingerprint="fp", agora="2026-09-05T20:00:00+00:00",
            sinais_ativacao={"interacao_humana": True}, dados_contexto={"percepcao": _Percepcao()},
        )
        self.assertEqual("core", retriever.calls[0]["entity_id"])
        self.assertEqual("m1", builder.kwargs["memorias_relevantes"][0]["memory_id"])

    def test_falha_retriever_degrada_para_contexto_sem_memoria(self):
        policy = FakePolicy(DecisaoAtivacaoCognitiva(True, MotivoAtivacaoCognitiva.INTERACAO_HUMANA))
        builder = FakeBuilder()
        gateway = FakeGateway(ResultadoInferencia(True, "ok", None, 2, "fake"))
        loop = ReactionLoopCognitivo(policy, builder, gateway, memory_retriever=FakeRetriever(error=RuntimeError("db")))
        loop.processar(fingerprint="fp", agora="2026-09-05T20:00:00+00:00", sinais_ativacao={}, dados_contexto={})
        self.assertEqual((), builder.kwargs["memorias_relevantes"])
