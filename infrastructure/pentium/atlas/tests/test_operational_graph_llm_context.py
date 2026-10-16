import json
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from types import SimpleNamespace

from infrastructure.pentium.atlas.operational_graph_llm_context import graph_context_for_llm
from infrastructure.pentium.atlas.cognitive_daemon import CognitiveDaemon

METRICS={"valencia":0.2,"ativacao":0.3,"estresse":0.4,"confianca":0.8,"engajamento":0.7,"curiosidade":0.5}
class GraphContextTests(unittest.TestCase):
    def test_current_measurements_and_trend_pass_to_llm(self):
        with tempfile.TemporaryDirectory() as folder:
            when=datetime(2026,10,15,14,0,tzinfo=timezone.utc)
            rows=[{"agent":"atlas","at":when.isoformat(),**METRICS},
                  {"agent":"atlas","at":(when-timedelta(minutes=2)).isoformat(),
                    **{**METRICS,"estresse":0.2}}]
            root=Path(folder)/"graph.json"
            root.write_text(json.dumps({"schema_version":1,"affect_series":rows,
              "observed_events_by_severity":{"critical":1,"warning":2},
              "nodes":[{"type":"agent","id":"agent:security-audit"}],
              "payload":{"password":"PRIVATE_NO"}}),encoding="utf-8")
            facts=graph_context_for_llm(root,now=when)
            self.assertEqual(facts[0]["metrics"]["estresse"],0.4)
            self.assertAlmostEqual(facts[1]["delta"]["estresse"],0.2)
            self.assertEqual(facts[1]["causality"],"unverified_temporal_association")
            self.assertEqual(facts[2]["counts"]["critical"],1)
            self.assertEqual(facts[3]["ids"],["agent:security-audit"])
            self.assertNotIn("PRIVATE_NO",json.dumps(facts))
            self.assertEqual(graph_context_for_llm(root,now=when+timedelta(hours=1)),())
    def test_snapshot_invalid_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"graph.json"
            p.write_text(json.dumps({"schema_version":1,"affect_series":[{
              "agent":"atlas","at":"2026-10-15T14:00:00+00:00",**{**METRICS,"estresse":float("nan")}}]}))
            self.assertEqual(graph_context_for_llm(p),())
    def test_live_cognitive_loop_receives_graph_context(self):
        observed=[]
        class Loop:
            def processar(self,**data):
                observed.append(data["dados_contexto"])
                return SimpleNamespace(ativado=False,razao="not_needed")
        class Publisher:
            def publish_phase(self,*args,**kwargs):pass
            def publish(self,*args,**kwargs):pass
        snapshot=SimpleNamespace(source_stimulus_id="stimulus-123",
          generated_at="2026-10-15T14:00:00+00:00",
          recent_changes=({"severity":"notice","kind":"status_changed","novelty":1.0},),
          affective_state=METRICS)
        rec=({"type":"atlas_affect_measurement","metrics":METRICS},)
        daemon=CognitiveDaemon(lambda:snapshot,lambda:{"assessment":object()},Loop(),Publisher(),
              graph_context_loader=lambda:rec)
        daemon.run_once()
        self.assertEqual(observed[0]["grafo_conhecimento"],rec)
    def test_broken_graph_cannot_block_regular_conversation(self):
        observed=[]
        class Loop:
            def processar(self,**data):
                observed.append(data["dados_contexto"])
                return SimpleNamespace(ativado=False,razao="not_needed")
        class Publisher:
            def publish_phase(self,*args,**kwargs):pass
            def publish(self,*args,**kwargs):pass
        snapshot=SimpleNamespace(source_stimulus_id="s4",
          generated_at="2026-10-15T14:00:00+00:00",
          recent_changes=({"severity":"notice","kind":"status_changed","novelty":1.0},),
          affective_state=METRICS)
        daemon=CognitiveDaemon(lambda:snapshot,lambda:{"assessment":object()},Loop(),Publisher(),
              graph_context_loader=lambda: (_ for _ in ()).throw(ValueError("bad_graph")))
        daemon.run_once()
        self.assertNotIn("grafo_conhecimento",observed[0])
if __name__=="__main__":unittest.main()
