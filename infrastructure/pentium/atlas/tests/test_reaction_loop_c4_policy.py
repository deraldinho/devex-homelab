import unittest
from types import SimpleNamespace

from infrastructure.pentium.atlas.capability_registry import CapabilityRegistry, CapabilitySpec
from infrastructure.pentium.atlas.policy_capabilities import PolicyCapabilities
from infrastructure.pentium.atlas.reaction_loop_cognitivo import ReactionLoopCognitivo
from infrastructure.pentium.atlas.modelo_contexto_cognitivo import MotivoAtivacaoCognitiva


class FakePolicy:
    def avaliar(self, **kwargs):
        return SimpleNamespace(ativar=True, motivo=MotivoAtivacaoCognitiva.INTERACAO_HUMANA, razao_bloqueio=None)
    def registrar_ativacao(self, *args, **kwargs):
        pass


class FakeBuilder:
    def construir(self, **kwargs):
        return SimpleNamespace()


class FakeGateway:
    def __init__(self, texto):
        self.texto = texto
    def inferir(self, contexto, tarefa):
        return SimpleNamespace(sucesso=True, texto=self.texto, backend="fake", duracao_ms=1)
class ReactionLoopC4PolicyTests(unittest.TestCase):
    def setUp(self):
        registry = CapabilityRegistry([
            CapabilitySpec("get_host_status", "READ", ("host",), tipos_parametros=(("host", "str"),)),
        ])
        self.cap_policy = PolicyCapabilities(registry, read_auto_allow=("get_host_status",), control_allow=())

    def test_intencao_valida_e_autorizada_e_exposta_sem_execucao(self):
        payload = '{"versao_schema":1,"texto":"Vou verificar.","resumo":null,"intencao":"get_host_status","parametros_intencao":{"host":"core"},"confianca":0.9,"motivo":"interacao_humana","requer_confirmacao":false}'
        loop = ReactionLoopCognitivo(FakePolicy(), FakeBuilder(), FakeGateway(payload), capability_policy=self.cap_policy)
        resposta = loop.processar(fingerprint="x", agora="2026-09-05T20:00:00+00:00", sinais_ativacao={}, dados_contexto={})
        self.assertEqual("get_host_status", resposta.intencao)
        self.assertTrue(resposta.intencao_autorizada)
        self.assertEqual({"host": "core"}, resposta.parametros_intencao)

    def test_saida_malformada_vira_fallback_sem_intencao(self):
        loop = ReactionLoopCognitivo(FakePolicy(), FakeBuilder(), FakeGateway("nao-json"), capability_policy=self.cap_policy)
        resposta = loop.processar(fingerprint="x", agora="2026-09-05T20:00:00+00:00", sinais_ativacao={}, dados_contexto={})
        self.assertEqual("saida_llm_invalida", resposta.razao)
        self.assertIsNone(resposta.intencao)
        self.assertFalse(resposta.intencao_autorizada)
