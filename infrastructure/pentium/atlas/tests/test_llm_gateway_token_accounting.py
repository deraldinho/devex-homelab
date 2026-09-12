import unittest
from infrastructure.pentium.atlas.llm_gateway import LLMGateway
from infrastructure.pentium.atlas.modelo_llm_gateway import ResultadoInferencia
from infrastructure.pentium.atlas.modelo_contexto_cognitivo import ContextoCognitivo, MotivoAtivacaoCognitiva

class Backend:
    def inferir(self, request):
        return ResultadoInferencia(True,'resposta curta',None,1,'fake')

class TokenAccountingTests(unittest.TestCase):
    def test_gateway_reports_estimated_input_and_output_tokens(self):
        seen=[]
        gateway=LLMGateway(Backend(),max_payload_bytes=10000,max_tokens_contexto=4000,token_recorder=lambda total:seen.append(total))
        ctx=ContextoCognitivo(1,'2026-09-12T19:00:00+00:00',MotivoAtivacaoCognitiva.INTERACAO_HUMANA,'core','ok','ok',None,{},'sereno',(),None,None,(),(),())
        gateway.inferir(ctx,'responder')
        self.assertEqual(1,len(seen))
        self.assertGreater(seen[0],0)
