import json, sys, unittest
from pathlib import Path
from tempfile import TemporaryDirectory
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import dashboard_collectors

class DashboardChatUiTests(unittest.TestCase):
    def test_ui_contains_chat_plan_and_operational_timeline(self):
        html=(ROOT/'dashboard.html').read_text(encoding='utf-8')
        for token in ('atlasChatHistory','atlasChatInput','atlasChatSend','actionPlanObjective','actionPlanConfidence','actionPlanActions','operationalTimeline','EventSource','/api/stream','/api/chat'):
            self.assertIn(token,html)
        self.assertNotIn('chain-of-thought',html.lower())

    def test_runtime_collector_exposes_safe_plan_and_chat_events(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp); runtime=root/'runtime.json'; plan=root/'plan.json'; events=root/'events.jsonl'; activity=root/'activity.jsonl'
            runtime.write_text(json.dumps({'schema_version':2,'generated_at':'now','source_stimulus_id':'s1','state':'OBSERVANDO','activity':'resultado_concluido','last_result':{'summary':'ok'}}),encoding='utf-8')
            plan.write_text(json.dumps({'schema_version':1,'plan_id':'p1','stimulus_id':'s1','objective':'responder','confidence':.9,'response_text':'Tudo certo','trigger_kind':'human_interaction','actions':[{'action_id':'a1','type':'CHAT_REPLY','target':None,'parameters':{},'status':'COMPLETED','reason':None}]}),encoding='utf-8')
            events.write_text(json.dumps({'id':1,'type':'chat_message','payload':{'role':'user','message':'Oi','secret':'x'}})+'\n'+json.dumps({'id':2,'type':'chat_message','payload':{'role':'atlas','message':'Tudo certo'}})+'\n',encoding='utf-8')
            activity.write_text('',encoding='utf-8')
            cfg={**dashboard_collectors.default_config(),'cognitive_runtime_path':str(runtime),'cognitive_activity_path':str(activity),'action_plan_path':str(plan),'dashboard_events_path':str(events)}
            data=dashboard_collectors.collect_cognitive_runtime(cfg)
        self.assertEqual('p1',data['action_plan']['plan_id']); self.assertEqual(2,len(data['chat_history'])); self.assertNotIn('secret',json.dumps(data))

if __name__=='__main__': unittest.main()
