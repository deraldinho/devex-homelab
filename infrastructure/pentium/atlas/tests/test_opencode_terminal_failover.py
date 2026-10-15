import tempfile,unittest
from pathlib import Path
from infrastructure.pentium.atlas.opencode_http_transport import OpenCodeHTTPTransport
from infrastructure.pentium.atlas.tests.test_opencode_http_transport import Reply
from infrastructure.pentium.atlas.opencode_inference_adapter import OpenCodeInferenceAdapter
from infrastructure.pentium.atlas.modelo_llm_gateway import (
    ErroInferencia,SolicitacaoInferencia)

class TerminalFailoverTests(unittest.TestCase):
    def setup_transport(self,folder,responses,calls):
        def opener(req,timeout):
            calls.append((req.full_url,req.get_method()))
            return Reply(responses.pop(0))
        return OpenCodeHTTPTransport(base_url="http://127.0.0.1:49374",
            password="test",directory=folder,opener=opener,
            journal_path=Path(folder)/"journal.json")
    def args(self):
        return {"model":"free","prompt":"code","context":"{}","max_tokens":100}
    def test_terminal_zero_cost_429_allows_fallback_without_repost(self):
        with tempfile.TemporaryDirectory() as folder:
            calls=[]
            responses=[{"data":{"id":"s1"}},{},
                       {"data":{"outcome":"failed","cost":0}},
                       {"data":[{"type":"assistant","error":{"status":429}}]}]
            t=self.setup_transport(folder,responses,calls)
            result=t(**self.args())
            self.assertEqual(result["status"],"unavailable")
            self.assertTrue(result["retry_safe"])
            self.assertTrue(result["terminal"])
            self.assertEqual(t.ledger.read()["state"],"failed")
            adapter=OpenCodeInferenceAdapter(model="free",
                transport=lambda **_:result,authorized_models={"free"})
            self.assertEqual(adapter.inferir(
                SolicitacaoInferencia(1,"code","{}",100)).erro,
                ErroInferencia.MODELO_INDISPONIVEL)
            self.assertEqual(t(**self.args())["status"],"unavailable")
            self.assertEqual(len(calls),4)
    def test_failed_with_cost_or_unknown_reason_stays_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            calls=[]
            responses=[{"data":{"id":"s1"}},{},
                       {"data":{"outcome":"failed","cost":0.02}}]
            t=self.setup_transport(folder,responses,calls)
            with self.assertRaises(TimeoutError):t(**self.args())
            self.assertEqual(t.ledger.read()["state"],"dispatch_uncertain")
    def test_router_switches_after_verified_terminal_failure(self):
        from infrastructure.pentium.atlas.governed_inference_router import GovernedInferenceRouter
        from infrastructure.pentium.atlas.free_model_selection import ModelOffer
        attempts=[]
        def first(**_):
            attempts.append("first")
            return {"status":"unavailable","terminal":True,"retry_safe":True,
                    "dispatched":True,"usage":{"cost":0},"session_id":"failed-id"}
        def second(**_):
            attempts.append("second")
            return {"status":"ok","text":"fallback worked","usage":{"cost":0},
                    "session_id":"second-id"}
        offers=[ModelOffer("opencode","first",0,0,True,frozenset({"code"}),9),
                ModelOffer("opencode","second",0,0,True,frozenset({"code"}),1)]
        backends={("opencode","first"):OpenCodeInferenceAdapter(
            model="first",transport=first,authorized_models={"first"}),
                  ("opencode","second"):OpenCodeInferenceAdapter(
            model="second",transport=second,authorized_models={"second"})}
        router=GovernedInferenceRouter(offers=offers,
            authorized={("opencode","first"),("opencode","second")},backends=backends)
        result=router.inferir(SolicitacaoInferencia(1,"code","{}",100))
        self.assertTrue(result.sucesso)
        self.assertEqual(attempts,["first","second"])
if __name__=="__main__":unittest.main()
