import unittest
from infrastructure.pentium.atlas.free_model_selection import ModelOffer
from infrastructure.pentium.atlas.governed_inference_router import GovernedInferenceRouter
from infrastructure.pentium.atlas.modelo_llm_gateway import SolicitacaoInferencia,ResultadoInferencia,ErroInferencia
class Backend:
    def __init__(self,result):self.result=result;self.calls=0
    def inferir(self,request):self.calls+=1;return self.result
class RouterTests(unittest.TestCase):
    def offer(self,name,quality=1,price=0):
        return ModelOffer("opencode",name,price,price,True,frozenset({"code"}),quality)
    def request(self):return SolicitacaoInferencia(1,"code","{}",100)
    def result(self,ok,error=None):
        return ResultadoInferencia(ok,"done" if ok else None,error,10,"fake")
    def test_fallback_on_explicit_unavailable(self):
        a=Backend(self.result(False,ErroInferencia.MODELO_INDISPONIVEL))
        b=Backend(self.result(True))
        events=[]
        router=GovernedInferenceRouter(offers=[self.offer("a",9),self.offer("b")],
            authorized={("opencode","a"),("opencode","b")},
            backends={("opencode","a"):a,("opencode","b"):b},telemetry=events.append)
        self.assertTrue(router.inferir(self.request()).sucesso)
        self.assertEqual((a.calls,b.calls,len(events)),(1,1,2))
        self.assertIsNone(events[0]["tokens_input"])
    def test_dont_replay_on_timeout(self):
        a=Backend(self.result(False,ErroInferencia.TIMEOUT));b=Backend(self.result(True))
        router=GovernedInferenceRouter(offers=[self.offer("a",9),self.offer("b")],
            authorized={("opencode","a"),("opencode","b")},backends={("opencode","a"):a,("opencode","b"):b})
        self.assertEqual(router.inferir(self.request()).erro,ErroInferencia.TIMEOUT)
        self.assertEqual(b.calls,0)
    def test_paid_or_unverified_never_dispatched(self):
        paid=Backend(self.result(True))
        router=GovernedInferenceRouter(offers=[self.offer("paid",price=1)],
            authorized={("opencode","paid")},backends={("opencode","paid"):paid})
        self.assertFalse(router.inferir(self.request()).sucesso)
        self.assertEqual(paid.calls,0)
if __name__=="__main__":unittest.main()
