import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cognitive_panel_certification import Evidence, certify

SHA='abc123'

class CognitivePanelCertificationTests(unittest.TestCase):
    def test_pass_requires_live_read_only_panel(self):
        ev=Evidence(SHA,SHA,'active','active','inactive','disabled',{'cognition':{'status':'available','observed_sha':SHA,'entity_id':'x99'}},{'POST':405,'PUT':405,'PATCH':405,'DELETE':405})
        result=certify(ev)
        self.assertTrue(result.physical_pass)
        self.assertEqual(result.marker,'ATLAS_DASHBOARD_COGNITIVE_PANEL_PHYSICAL_PASS')

    def test_rejects_voice_or_write_path(self):
        ev=Evidence(SHA,SHA,'active','active','active','enabled',{'cognition':{'status':'available','observed_sha':SHA,'entity_id':'x99'}},{'POST':200})
        result=certify(ev)
        self.assertFalse(result.physical_pass)
        self.assertIn('voice_not_paused',result.failures)
        self.assertIn('write_method_accepted',result.failures)

if __name__=='__main__': unittest.main()
