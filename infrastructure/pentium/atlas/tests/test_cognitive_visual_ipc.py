import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from infrastructure.pentium.atlas.affective_runtime import AffectiveRuntime
from infrastructure.pentium.atlas.modelo_visual_atlas import EstadoInteracaoVisual
from infrastructure.pentium.atlas.cognitive_daemon import CognitiveDaemon

NOW='2026-09-08T18:30:00+00:00'

class FakeCompositor:
    def __init__(self): self.interactions=[]
    def compor(self,result,interaction,**kwargs): self.interactions.append(interaction); return SimpleNamespace(marker=len(self.interactions))
class FakePublisher:
    def publicar(self,visual): pass

class CognitiveVisualMuxTests(unittest.TestCase):
    def test_cognitive_thinking_merges_without_erasing_voice_flags(self):
        comp=FakeCompositor(); rt=AffectiveRuntime(comp,FakePublisher(),interacao_inicial=EstadoInteracaoVisual(atualizado_em=NOW))
        rt.atualizar_resultado(object())
        rt.atualizar_interacao(EstadoInteracaoVisual(ouvindo=True,atualizado_em=NOW))
        rt.atualizar_cognicao(EstadoInteracaoVisual(pensando=True,atualizado_em=NOW))
        effective=comp.interactions[-1]
        self.assertTrue(effective.ouvindo); self.assertTrue(effective.pensando); self.assertFalse(effective.falando)
        rt.atualizar_cognicao(EstadoInteracaoVisual(pensando=False,atualizado_em=NOW))
        effective=comp.interactions[-1]
        self.assertTrue(effective.ouvindo); self.assertFalse(effective.pensando)

class CognitiveDaemonVisualTests(unittest.TestCase):
    def test_daemon_emits_thinking_true_then_false_around_inference(self):
        states=[]
        snap=SimpleNamespace(source_stimulus_id='s1',generated_at=NOW,recent_changes=({'severity':'notice','kind':'status_changed','novelty':.9},),affective_state={})
        class Loop:
            def processar(self,**kwargs):
                kwargs["on_inference"](True)
                self.seen=list(states)
                kwargs["on_inference"](False)
                return SimpleNamespace(ativado=True,razao=None)
        class Pub:
            def publish(self,*args): pass
        daemon=CognitiveDaemon(lambda:snap,lambda:{},Loop(),Pub(),visual_state_sink=lambda state:states.append(state))
        daemon.run_once()
        self.assertEqual([True,False],[x.pensando for x in states])

class CognitiveIpcPackagingTests(unittest.TestCase):
    def test_observation_daemon_owns_distinct_cognitive_socket(self):
        root=Path(__file__).resolve().parents[1]
        obs=(root/'observation_daemon.py').read_text(encoding='utf-8')
        cog=(root/'cognitive_daemon.py').read_text(encoding='utf-8')
        self.assertIn('cognitive-interaction.sock',obs)
        self.assertIn('cognitive-interaction.sock',cog)
        self.assertIn('atualizar_cognicao',obs)

if __name__=='__main__': unittest.main()
