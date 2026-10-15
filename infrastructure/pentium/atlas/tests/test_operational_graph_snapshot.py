import json
import tempfile
import unittest
from pathlib import Path
from infrastructure.pentium.atlas.operational_affective_graph import OperationalAffectiveGraph
from infrastructure.pentium.atlas.operational_graph_snapshot import ingest_current,publish_graph

STATE={"valencia":0.1,"ativacao":0.4,"estresse":0.3,"confianca":0.6,"engajamento":0.5,
  "curiosidade":0.7,"atualizado_em":"2026-10-15T12:00:10+00:00",
  "foco_atencao":"please do not persist private data"}
STIM={"stimulus_id":"s1","source":"host.health","kind":"health",
   "severity":"critical","timestamp":"2026-10-15T12:00:00+00:00",
   "correlation_id":"c1","payload":{"token":"secret-nvapi"}}
class GraphIngestionTests(unittest.TestCase):
  def setUp(self):
    self.temp=tempfile.TemporaryDirectory()
    self.root=Path(self.temp.name)
    self.graph=OperationalAffectiveGraph(self.root/"graph.sqlite3")
    (self.root/"affective-state.json").write_text(json.dumps({"versao_esquema":1,"estado":STATE}))
    (self.root/"cognitive-observation-context.json").write_text(json.dumps({
      "source_stimulus_id":"s1","generated_at":"2026-10-15T12:00:15+00:00",
      "recent_changes":[STIM]}))
  def tearDown(self):self.temp.cleanup()
  def test_ingest_and_export_without_private_content(self):
    info=ingest_current(self.graph,runtime=self.root)
    self.assertEqual(info["accepted_observations"],1)
    self.assertTrue(info["correlation_linked"])
    result=publish_graph(self.graph,self.root/"graph.json")
    self.assertGreater(result["nodes"],0)
    exported=(self.root/"graph.json").read_text()
    self.assertNotIn("secret-nvapi",exported)
    self.assertNotIn("do not persist",exported)
    self.assertEqual(json.loads(exported)["observed_events_by_severity"]["critical"],1)
    ingest_current(self.graph,runtime=self.root)
    self.assertEqual(len(self.graph.export()["affect_series"]),1)
  def test_rejects_invalid_recent_event_without_stopping(self):
    context=json.loads((self.root/"cognitive-observation-context.json").read_text())
    context["recent_changes"].append({"severity":"secret"})
    (self.root/"cognitive-observation-context.json").write_text(json.dumps(context))
    result=ingest_current(self.graph,runtime=self.root)
    self.assertEqual(result["accepted_observations"],1)
    self.assertEqual(result["rejected_observations"],1)
  def test_no_stale_correlation(self):
    ctx=json.loads((self.root/"cognitive-observation-context.json").read_text())
    ctx["generated_at"]="2026-10-15T14:00:00+00:00"
    (self.root/"cognitive-observation-context.json").write_text(json.dumps(ctx))
    info=ingest_current(self.graph,runtime=self.root)
    self.assertFalse(info["correlation_linked"])
    self.assertNotIn("OBSERVED_DURING",[e["type"] for e in self.graph.export()["edges"]])
  def test_rejects_corrupt_affective_state(self):
    p=self.root/"affective-state.json"
    d=json.loads(p.read_text());d["versao_esquema"]=9;p.write_text(json.dumps(d))
    with self.assertRaises(ValueError):ingest_current(self.graph,runtime=self.root)
if __name__=="__main__":unittest.main()
