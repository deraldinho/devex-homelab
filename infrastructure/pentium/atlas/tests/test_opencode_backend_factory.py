import tempfile,unittest
from unittest.mock import patch
from infrastructure.pentium.atlas.free_model_selection import ModelOffer
from infrastructure.pentium.atlas.modelo_llm_gateway import SolicitacaoInferencia
from infrastructure.pentium.atlas.opencode_backend_factory import make_opencode_backend_factory

class FactoryTests(unittest.TestCase):
    def offer(self,name="free",price=0,verified=True,provider="opencode"):
        return ModelOffer(provider,name,price,price,verified,frozenset({"code"}),7)
    def config(self,offers,authorized,folder,telemetry=None):
        return dict(offers=offers,authorized=authorized,
                    base_url="http://127.0.0.1:49374",password="test",
                    directory=folder,journal_dir=folder,telemetry=telemetry)
    def test_unpriced_or_unauthorized_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            for offer,allowed in (
                (self.offer(price=None),{("opencode","free")}),
                (self.offer(price=1),{("opencode","free")}),
                (self.offer(verified=False),{("opencode","free")}),
                (self.offer(),set())):
                with self.assertRaises(ValueError):
                    make_opencode_backend_factory(**self.config([offer],allowed,folder))
    def test_opt_in_backend_uses_trusted_model_and_telemetry(self):
        with tempfile.TemporaryDirectory() as folder:
            selected=[]
            events=[]
            def mock_pool(**kwargs):
                selected.append(kwargs["authorized_free_models"])
                def answer(**request):
                    return {"status":"ok","text":"safe answer","usage":{
                        "input":5,"output":8,"cache_read":2,"cost":0}}
                return answer
            with patch("infrastructure.pentium.atlas.opencode_backend_factory.OpenCodeSessionPool",
                       side_effect=mock_pool):
                build=make_opencode_backend_factory(**self.config(
                    [self.offer()],{("opencode","free")},folder,events.append))
                backend=build(None)
                result=backend.inferir(SolicitacaoInferencia(1,"code","{}",100))
            self.assertTrue(result.sucesso)
            self.assertEqual(result.tokens_input,5)
            self.assertEqual(events[0]["tokens_output"],8)
            self.assertEqual(selected[0],frozenset({"free"}))
if __name__=="__main__":unittest.main()
