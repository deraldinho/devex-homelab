import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import dashboard_collectors as dc


class DashboardCognitiveObservableTests(unittest.TestCase):
    def test_collect_runtime_v2_exposes_safe_observable_state(self):
        with TemporaryDirectory() as tmp:
            base=Path(tmp); runtime=base/'runtime.json'; timeline=base/'activity.jsonl'
            runtime.write_text(json.dumps({
                'schema_version':2,'generated_at':'2026-09-08T23:00:00+00:00','source_stimulus_id':'s1','entity_id':'x99',
                'state':'OBSERVANDO','activity':'resultado_concluido','task':'formular_resposta_cognitiva','motivo':'mudanca_estado','detail':'mudanca detectada',
                'last_result':{'activated':True,'reason':None,'motivo':'mudanca_estado','summary':'x99 mudou','response_preview':'Vou verificar.','intention':'get_host_status','confidence':.82,'backend':'llama_cpp','duration_ms':321,'requires_confirmation':False,'intention_authorized':True}
            }),encoding='utf-8')
            timeline.write_text(json.dumps({'timestamp':'2026-09-08T23:00:00+00:00','source_stimulus_id':'s1','state':'OBSERVANDO','activity':'resultado_concluido','motivo':'mudanca_estado','summary':'x99 mudou','intention':'get_host_status','confidence':.82})+'\n',encoding='utf-8')
            cfg={'cognitive_runtime_path':str(runtime),'cognitive_activity_path':str(timeline)}
            data=dc.collect_cognitive_runtime(cfg); events=dc.collect_cognitive_activity(cfg)
            self.assertEqual('OBSERVANDO',data['state'])
            self.assertEqual('resultado_concluido',data['activity'])
            self.assertEqual('x99 mudou',data['summary'])
            self.assertEqual('Vou verificar.',data['response_preview'])
            self.assertEqual('get_host_status',data['intention'])
            self.assertTrue(data['intention_authorized'])
            self.assertEqual(.82,data['confidence'])
            self.assertEqual(1,len(events))
            self.assertEqual('resultado_concluido',events[0]['activity'])
            self.assertNotIn('parameters',data)
            self.assertNotIn('prompt',json.dumps(data).lower())

    def test_ui_contains_current_activity_and_cognitive_timeline(self):
        html=(ROOT/'dashboard.html').read_text(encoding='utf-8')
        for token in ('cogNowState','cogNowActivity','cogNowTask','cogNowSummary','cogNowIntention','cogTimeline','renderCognitiveActivity'):
            self.assertIn(token,html)


if __name__=='__main__':
    unittest.main()
