import unittest
from infrastructure.pentium.atlas.opencode_inference_adapter import OpenCodeInferenceAdapter
from infrastructure.pentium.atlas.modelo_llm_gateway import SolicitacaoInferencia,ErroInferencia
from infrastructure.pentium.atlas.governed_inference_router import GovernedInferenceRouter
from infrastructure.pentium.atlas.free_model_selection import ModelOffer

class AdapterTests(unittest.TestCase):
    def request(self):return SolicitacaoInferencia(1,"code","{}",100)
    def adapter(self,transport):
        return OpenCodeInferenceAdapter(model="free-a",transport=transport,authorized_models={"free-a"})
    def test_success(self):
        a=self.adapter(lambda **kw:{"status":"ok","text":"worked"})
        self.assertEqual(a.inferir(self.request()).texto,"worked")
    def test_refuses_unknown_model(self):
        with self.assertRaises(ValueError):
            OpenCodeInferenceAdapter(model="paid",transport=lambda **kw:{},authorized_models={"free-a"})
    def test_timeout_is_not_replayed(self):
        calls=[]
        def timeout(**kw):calls.append(1);raise TimeoutError()
        a=self.adapter(timeout)
        b=self.adapter(lambda **kw:{"status":"ok","text":"second"})
        offers=[ModelOffer("opencode","free-a",0,0,True,frozenset({"code"}),9),
                ModelOffer("opencode","free-b",0,0,True,frozenset({"code"}),1)]
        router=GovernedInferenceRouter(offers=offers,authorized={("opencode","free-a"),("opencode","free-b")},
                backends={("opencode","free-a"):a,("opencode","free-b"):b})
        self.assertEqual(router.inferir(self.request()).erro,ErroInferencia.TIMEOUT)
        self.assertEqual(len(calls),1)
    def test_explicit_pre_dispatch_unavailable(self):
        a=self.adapter(lambda **kw:{"status":"unavailable","dispatched":False})
        self.assertEqual(a.inferir(self.request()).erro,ErroInferencia.MODELO_INDISPONIVEL)
    def test_unknown_outcome_fails_closed(self):
        a=self.adapter(lambda **kw:{"status":"unavailable"})
        self.assertEqual(a.inferir(self.request()).erro,ErroInferencia.SAIDA_INVALIDA)
if __name__=="__main__":unittest.main()
