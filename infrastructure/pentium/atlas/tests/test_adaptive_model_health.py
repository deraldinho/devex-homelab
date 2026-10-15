import tempfile
from contextlib import closing
import sqlite3
import unittest
from pathlib import Path
from types import SimpleNamespace
from infrastructure.pentium.atlas.adaptive_model_health import AdaptiveModelHealth,ModelSignal
from infrastructure.pentium.atlas.free_model_selection import ModelOffer
from infrastructure.pentium.atlas.governed_inference_router import GovernedInferenceRouter
from infrastructure.pentium.atlas.modelo_llm_gateway import ResultadoInferencia,ErroInferencia

CLOCK=1_800_000_000
def offer(name,price=0):
    return ModelOffer("nous",name,price,price,price==0,frozenset({"code"}))
class FakeBackend:
    def __init__(self,name,result,events):self.name,self.result,self.events=name,result,events
    def inferir(self,request):self.events.append(self.name);return self.result
def health(folder,now=lambda:CLOCK,**kwargs):
    return AdaptiveModelHealth(Path(folder)/"signals.sqlite3",now=now,**kwargs)
class AdaptiveHealthTests(unittest.TestCase):
    def test_success_latency_reorders_without_fabricated_quota(self):
        with tempfile.TemporaryDirectory() as tmp:
            h=health(tmp); a=offer("a");b=offer("b")
            self.assertEqual(h.rank([a,b],task="code"),(a,b))
            h.record(ModelSignal("nous","b",True,100,observed_at=CLOCK))
            self.assertEqual(h.rank([a,b],task="code"),(b,a))
            self.assertEqual(h.stats("nous","b")["quota_status"],"unknown")
    def test_known_zero_quota_blocks_only_affected_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            h=health(tmp);a=offer("a");b=offer("b")
            h.record(ModelSignal("nous","a",False,100,"quota_exhausted",0,CLOCK))
            self.assertEqual(h.rank([a,b],task="code"),(b,))
    def test_429_cooldown_expires(self):
        current=[CLOCK]
        with tempfile.TemporaryDirectory() as tmp:
            h=health(tmp,now=lambda:current[0])
            a=offer("a")
            h.record(ModelSignal("nous","a",False,100,"rate_limit",None,CLOCK))
            self.assertEqual(h.rank([a],task="code"),())
            current[0]+=3601
            self.assertEqual(h.rank([a],task="code"),(a,))
    def test_expired_metrics_do_not_bias_order(self):
        current=[CLOCK]
        with tempfile.TemporaryDirectory() as tmp:
            h=health(tmp,now=lambda:current[0],ttl_seconds=60)
            a=offer("a");b=offer("b")
            h.record(ModelSignal("nous","b",True,1,observed_at=CLOCK))
            current[0]+=80
            self.assertEqual(h.rank([a,b],task="code"),(a,b))
    def test_migrates_existing_ledger_in_place(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'signals.sqlite3'
            with closing(sqlite3.connect(path)) as db, db:
                db.execute('CREATE TABLE signals(id INTEGER PRIMARY KEY, provider TEXT NOT NULL, model TEXT NOT NULL, success INTEGER NOT NULL, latency_ms INTEGER, error TEXT, quota_remaining INTEGER, observed_at REAL NOT NULL)')
            h=AdaptiveModelHealth(path,now=lambda:CLOCK)
            h.record(ModelSignal('nous','a',True,150,event_id='one'))
            self.assertEqual(h.stats('nous','a')['samples'],1)
    def test_session_signal_deduplicates_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            h=health(tmp)
            signal=ModelSignal('nous','a',True,200,event_id='safe-session-id')
            h.record(signal)
            h.record(signal)
            self.assertEqual(h.stats('nous','a')['samples'],1)
            with self.assertRaises(ValueError):
                h.record(ModelSignal('nous','a',True,200,event_id='prompt with spaces'))
    def test_graded_quality_requires_three_distinct_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            h=health(tmp)
            a=offer('a');b=offer('b')
            for i in range(2):
                h.record_evaluation('nous','b','code',str(i),True)
            self.assertEqual(h.rank([a,b],task='code'),(a,b))
            h.record_evaluation('nous','b','code','case-3',True)
            h.record_evaluation('nous','b','code','case-3',False)
            self.assertEqual(h.quality('nous','b','code'),(1.0,3))
            self.assertEqual(h.rank([a,b],task='code'),(b,a))
            self.assertEqual(h.rank([a,b],task='general'),(a,b))
    def test_invalid_samples_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            h=health(tmp)
            with self.assertRaises(ValueError):
                h.record(ModelSignal("nous","a",False,100,"unknown_error",None,CLOCK))
            with self.assertRaises(ValueError):
                h.record(ModelSignal("nous","a",True,-5))
    def test_router_never_admits_paid_and_preserves_no_replay_on_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            h=health(tmp)
            a,b,paid=offer("a"),offer("b"),offer("paid",0.01)
            h.record(ModelSignal("nous","a",False,10,"rate_limit",None,CLOCK))
            calls=[]
            timeout=ResultadoInferencia(False,None,ErroInferencia.TIMEOUT,1300,"a")
            success=ResultadoInferencia(True,"ok",None,300,"b")
            router=GovernedInferenceRouter(offers=[a,b,paid],
                authorized={("nous","a"),("nous","b"),("nous","paid")},
                backends={("nous","a"):FakeBackend("a",success,calls),
                          ("nous","b"):FakeBackend("b",timeout,calls),
                          ("nous","paid"):FakeBackend("paid",success,calls)},
                adaptive_health=h)
            out=router.inferir(SimpleNamespace(tarefa="code"))
            self.assertFalse(out.sucesso)
            self.assertEqual(calls,["b"])
    def test_router_learns_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            h=health(tmp)
            events=[]
            a,b=offer("a"),offer("b")
            router=GovernedInferenceRouter(offers=[a,b],authorized={("nous","a"),("nous","b")},
              backends={("nous","a"):FakeBackend("a",ResultadoInferencia(True,"ok",None,5,"a"),events),
                        ("nous","b"):FakeBackend("b",ResultadoInferencia(True,"ok",None,3,"b"),events)},
              adaptive_health=h)
            router.inferir(SimpleNamespace(tarefa="code"))
            self.assertEqual(h.stats("nous","a")["samples"],1)
            self.assertEqual(events,["a"])
if __name__=="__main__":unittest.main()
