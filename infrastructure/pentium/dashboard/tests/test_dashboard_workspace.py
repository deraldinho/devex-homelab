import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import dashboard_collectors as dc


class DashboardWorkspaceTests(unittest.TestCase):
    def test_collect_workspace_economy_is_read_only_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'workspace-economy-health.json'
            path.write_text(json.dumps({
                'schema_version':1,'status':'healthy','expected_sha':'a'*40,
                'workspace':{'files':4,'bytes':1200,'max_files':2048,'max_bytes':134217728},
                'self_work':{'active':True,'state':'WORKING','objective':'organizar notas','operations_used':2,'inferences_used':1},
                'economy':{'mode':'normal','tokens_used':900,'window_budget':120000,'routes':{'deterministic':8,'llm':1,'no_inference_required':4}},
            }),encoding='utf-8')
            cfg=dc.default_config()|{'workspace_economy_path':str(path)}
            out=dc.collect_workspace_economy(cfg)
        self.assertEqual('healthy',out['status'])
        self.assertEqual('WORKING',out['self_work']['state'])
        self.assertEqual(8,out['economy']['routes']['deterministic'])
        self.assertNotIn('content',json.dumps(out))

    def test_dashboard_html_contains_workspace_read_only_panel(self):
        html=(ROOT/'dashboard.html').read_text(encoding='utf-8')
        for token in ('workspacePanel','workspaceUsage','selfWorkState','tokenEconomyMode','avoidedInferenceCount'):
            self.assertIn(token,html)

if __name__=='__main__': unittest.main()
