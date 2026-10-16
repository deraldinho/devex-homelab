import tempfile
import unittest
from pathlib import Path
from atlas_native_workflow import inspect
from atlas_native_free_runner import make_free_runner

ROOT=Path(__file__).resolve().parent

class FreeRunnerTests(unittest.TestCase):
    def test_refuses_unattested_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PermissionError):
                make_free_runner(api=lambda *a:None, state_path=Path(tmp)/"state.json",
                                 model_manager_type=lambda *a,**k:None,sandbox_attestation={})
    def test_injected_model_manager_called_only_on_valid_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempts=[]
            class FakeManager:
                def __init__(self,api,**opts):
                    attempts.append(opts)
                def run(self,**kwargs):
                    attempts.append(kwargs)
                    return {"status":"succeeded","cost":0,"text":"review evidence"}
            attestation=dict(os_enforced=True,network_restricted=True,
                             secrets_excluded=True,read_only_tools=True,
                             snapshot_root=str(ROOT))
            runner=make_free_runner(api=lambda *a:None,state_path=Path(tmp)/"state.json",
                       model_manager_type=FakeManager,sandbox_attestation=attestation)
            _,fingerprint=inspect(ROOT)
            answer=runner(dict(project_root=str(ROOT),fingerprint=fingerprint,read_only=True,
                               execution_authorized=False,role="qa",task_id="fixture"))
            self.assertEqual(answer["status"],"succeeded")
            self.assertEqual(len(attempts),2)
            self.assertEqual(attempts[1]["agent"],"plan")
            with self.assertRaises(PermissionError):
                runner(dict(project_root=str(ROOT),fingerprint="bad",read_only=True,
                            execution_authorized=False,role="qa",task_id="fixture"))
            self.assertEqual(len(attempts),2)
