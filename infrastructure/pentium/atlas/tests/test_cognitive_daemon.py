import unittest
from pathlib import Path
from types import SimpleNamespace

from infrastructure.pentium.atlas.cognitive_daemon import CognitiveDaemon

class FakeLoop:
    def __init__(self,response): self.response=response; self.calls=[]
    def processar(self,**kwargs): self.calls.append(kwargs); return self.response

class FakePublisher:
    def __init__(self): self.items=[]
    def publish(self,snapshot,response): self.items.append((snapshot,response))

class CognitiveDaemonTests(unittest.TestCase):
    def snapshot(self, sid='s1', severity='notice', kind='status_changed', novelty=.9, affective=None):
        return SimpleNamespace(source_stimulus_id=sid,generated_at='2026-09-08T18:00:00+00:00',recent_changes=({'severity':severity,'kind':kind,'novelty':novelty},),affective_state=affective or {'valencia':.5,'ativacao':.4,'estresse':.2,'confianca':.7,'engajamento':.5,'curiosidade':.6})

    def test_new_snapshot_invokes_loop_and_publishes_once(self):
        snap=self.snapshot(); loop=FakeLoop(SimpleNamespace(ativado=True,razao=None)) ; pub=FakePublisher()
        daemon=CognitiveDaemon(lambda:snap, lambda:{'assessment':object()}, loop, pub)
        result=daemon.run_once()
        self.assertTrue(result.ativado); self.assertEqual(1,len(loop.calls)); self.assertEqual(1,len(pub.items))
        self.assertIsNone(daemon.run_once()); self.assertEqual(1,len(loop.calls))

    def test_signals_derive_critical_recovery_state_change_and_novelty(self):
        snap=SimpleNamespace(source_stimulus_id='s2',generated_at='2026-09-08T18:00:00+00:00',recent_changes=(
            {'severity':'critical','kind':'status_changed','novelty':.8}, {'severity':'notice','kind':'recovered','novelty':.5}),affective_state={'valencia':.5,'ativacao':.4,'estresse':.2,'confianca':.7,'engajamento':.5,'curiosidade':.6})
        loop=FakeLoop(SimpleNamespace(ativado=True,razao=None)); daemon=CognitiveDaemon(lambda:snap,lambda:{},loop,FakePublisher())
        daemon.run_once(); signals=loop.calls[0]['sinais_ativacao']
        self.assertTrue(signals['criticidade']); self.assertTrue(signals['recuperacao_importante']); self.assertTrue(signals['mudanca_estado']); self.assertEqual(.8,signals['novidade'])

    def test_affective_delta_is_bounded_between_snapshots(self):
        snaps=iter([self.snapshot('a',affective={'valencia':.5,'ativacao':.2,'estresse':.1,'confianca':.8,'engajamento':.2,'curiosidade':.3}),self.snapshot('b',affective={'valencia':.5,'ativacao':.7,'estresse':.1,'confianca':.8,'engajamento':.2,'curiosidade':.3})])
        loop=FakeLoop(SimpleNamespace(ativado=True,razao=None)); daemon=CognitiveDaemon(lambda:next(snaps),lambda:{},loop,FakePublisher())
        daemon.run_once(); daemon.run_once(); self.assertAlmostEqual(.5,loop.calls[1]['sinais_ativacao']['delta_afetivo'])

class CognitiveDaemonPackagingTests(unittest.TestCase):
    def test_daemon_wires_resident_llama_server_and_service(self):
        root=Path(__file__).resolve().parents[1]
        source=(root/'cognitive_daemon.py').read_text(encoding='utf-8')
        install=(root/'install-user.sh').read_text(encoding='utf-8')
        unit=(root/'atlas-cognitive.service').read_text(encoding='utf-8')
        for token in ('LlamaCppServerRuntime','LlamaCppResidentBackend','ReactionLoopCognitivo','HumanContextProvider'):
            self.assertIn(token,source)
        self.assertIn('atlas-cognitive.service',install); self.assertIn('python3 -m atlas.cognitive_daemon',unit)
        self.assertIn('restart atlas-cognitive.service',install); self.assertNotIn('restart atlas-voice.service',install)
        self.assertIn('EnvironmentFile=-%h/pentium-agent/atlas/runtime/observation.env',unit)

    def test_repository_llm_config_points_to_installed_runtime_model(self):
        import json
        root=Path(__file__).resolve().parents[1]
        cfg=json.loads((root/'config_llm.json').read_text(encoding='utf-8'))
        self.assertEqual('runtime/llama/models/Qwen3-0.6B-Q4_0.gguf',cfg['modelo_path'])

if __name__=='__main__': unittest.main()
