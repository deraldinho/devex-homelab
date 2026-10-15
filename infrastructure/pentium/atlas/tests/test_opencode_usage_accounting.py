import unittest
from infrastructure.pentium.atlas.opencode_usage import extract_usage
from infrastructure.pentium.atlas.opencode_inference_adapter import OpenCodeInferenceAdapter
from infrastructure.pentium.atlas.modelo_llm_gateway import (
    ErroInferencia,ResultadoInferencia,SolicitacaoInferencia)
from infrastructure.pentium.atlas.llm_gateway import LLMGateway
from infrastructure.pentium.atlas.modelo_contexto_cognitivo import ContextoCognitivo,MotivoAtivacaoCognitiva

class UsageTests(unittest.TestCase):
    def test_real_provider_counters(self):
        state={"cost":0,"tokens":{"input":4321,"output":51,"reasoning":37,
                                  "cache":{"read":13120,"write":0}}}
        result=extract_usage(state)
        self.assertEqual(result["cache_read"],13120)
        self.assertEqual(result["cost"],0.0)
        self.assertEqual(result["source"],"opencode-session")
    def test_rejects_invalid_counts(self):
        result=extract_usage({"cost":-1,"tokens":{"input":True,"output":-3}})
        self.assertIsNone(result)
    def test_adapter_records_real_usage(self):
        def responder(**_):
            return {"status":"ok","text":"reply","usage":{"input":5,"output":7,
                "cache_read":20,"cost":0}}
        adapter=OpenCodeInferenceAdapter(model="free",transport=responder,
            authorized_models={"free"})
        result=adapter.inferir(SolicitacaoInferencia(1,"code","{}",100))
        self.assertTrue(result.sucesso)
        self.assertEqual((result.tokens_input,result.tokens_output,result.tokens_cache_read),(5,7,20))
    def test_paid_result_is_halted_not_fallback(self):
        adapter=OpenCodeInferenceAdapter(model="free",
            transport=lambda **_:{"status":"ok","text":"unexpected","usage":{"cost":0.01}},
            authorized_models={"free"})
        result=adapter.inferir(SolicitacaoInferencia(1,"code","{}",100))
        self.assertFalse(result.sucesso)
        self.assertEqual(result.erro,ErroInferencia.LIMITE_EXCEDIDO)
    def test_gateway_prefers_provider_usage_over_estimate(self):
        class MeasuredBackend:
            def inferir(self,_):
                return ResultadoInferencia(True,"ok",None,1,"fake",
                    tokens_input=5,tokens_output=7,tokens_cache_read=20,custo_usd=0)
        seen=[]
        gateway=LLMGateway(MeasuredBackend(),max_payload_bytes=10000,
            max_tokens_contexto=4000,token_recorder=seen.append)
        ctx=ContextoCognitivo(1,'2026-09-12T19:00:00+00:00',
            MotivoAtivacaoCognitiva.INTERACAO_HUMANA,'core','ok','ok',
            None,{},'sereno',(),None,None,(),(),())
        gateway.inferir(ctx,"code")
        self.assertEqual(seen,[32])
if __name__=="__main__":unittest.main()
