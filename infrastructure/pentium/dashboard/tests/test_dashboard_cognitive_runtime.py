import json,sys,unittest
from pathlib import Path
from tempfile import TemporaryDirectory
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));import dashboard_collectors as dc

class DashboardCognitiveRuntimeTests(unittest.TestCase):
    def test_collect_cognitive_runtime_exposes_only_safe_metadata(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'cog.json';p.write_text(json.dumps({'schema_version':1,'generated_at':'2026-09-08T18:00:00+00:00','source_stimulus_id':'s1','activated':True,'reason':None,'motivo':'mudanca_estado','texto':'segredo','resumo':'resumo privado','intencao':None,'confianca':.8,'backend':'llama_server','duracao_ms':123,'requer_confirmacao':False,'intencao_autorizada':False}),encoding='utf-8')
            data=dc.collect_cognitive_runtime({'cognitive_runtime_path':str(p)})
        self.assertEqual(data['status'],'available');self.assertEqual(data['backend'],'llama_server');self.assertEqual(data['duration_ms'],123);self.assertTrue(data['activated'])
        self.assertNotIn('texto',data);self.assertNotIn('resumo',data)

    def test_collect_status_exposes_cognitive_service(self):
        with TemporaryDirectory() as tmp:
            base=Path(tmp); cfg=dc.default_config()|{'visual_state_path':str(base/'none.json'),'cognitive_snapshot_path':str(base/'none2.json'),'cognitive_health_path':str(base/'none3.json'),'cognitive_runtime_path':str(base/'none4.json'),'health_path':str(base/'none5.json'),'voice_config_path':str(base/'none6.json'),'deploy_sha_path':str(base/'none7')}
            status=dc.collect_status(cfg,command_runner=lambda cmd,t: dc.CommandResult(0,'active\n' if 'is-active' in cmd else 'enabled\n',''))
        self.assertIn('cognitive',status['services']); self.assertIn('cognitive_runtime',status)

    def test_ui_contains_qwen_runtime_metadata(self):
        html=(ROOT/'dashboard.html').read_text(encoding='utf-8')
        for token in ('qwenRuntime','qwenBackend','qwenLatency','cognitive_runtime'):
            self.assertIn(token,html)

if __name__=='__main__':unittest.main()
