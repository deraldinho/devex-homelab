import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from infrastructure.pentium.atlas.action_executors import ActionExecutorRegistry
from infrastructure.pentium.atlas.action_plan import ActionStatus
from infrastructure.pentium.atlas.action_plan_store import ActionPlanStore
from infrastructure.pentium.atlas.action_planner import ActionPlanner
from infrastructure.pentium.atlas.action_policy import ActionPolicy
from infrastructure.pentium.atlas.capability_registry import atlas_capability_registry
from infrastructure.pentium.atlas.cognitive_daemon import CognitiveDaemon
from infrastructure.pentium.atlas.policy_capabilities import PolicyCapabilities


class Loop:
    def processar(self, **kwargs):
        return SimpleNamespace(ativado=True,razao=None,motivo="interacao_humana",texto="Oi.",resumo="responder",confianca=.9,intencao=None,parametros_intencao=None,requer_confirmacao=False,solicitar_fala=False)


class Publisher:
    def publish_phase(self,*args,**kwargs): pass
    def publish(self,*args,**kwargs): pass


class CognitiveActionRuntimeTests(unittest.TestCase):
    def test_valid_cognitive_result_creates_persists_and_executes_plan(self):
        snap=SimpleNamespace(source_stimulus_id="s1",entity_id="x99",generated_at="2026-09-08T18:00:00+00:00",recent_changes=(),affective_state={})
        caps=PolicyCapabilities(atlas_capability_registry(),read_auto_allow=("get_host_status",),control_allow=())
        events=[]
        with TemporaryDirectory() as tmp:
            root=Path(tmp); store=ActionPlanStore(root/"current.json",root/"history.jsonl")
            daemon=CognitiveDaemon(lambda:snap,lambda:{},Loop(),Publisher(),planner=ActionPlanner(),action_policy=ActionPolicy(caps),action_executor=ActionExecutorRegistry(),action_store=store,event_sink=lambda kind,payload:events.append((kind,payload)))
            result=daemon.run_once(); plan=store.load_current()
        self.assertEqual(result.texto,plan.response_text)
        self.assertEqual(["plan_created","action_status"],[x[0] for x in events[:2]])
        self.assertTrue(any(a.status in {ActionStatus.COMPLETED,ActionStatus.FAILED,ActionStatus.BLOCKED,ActionStatus.CANCELLED} for a in plan.actions))

    def test_degraded_cognitive_result_does_not_invent_plan(self):
        class BadLoop:
            def processar(self,**kwargs): return SimpleNamespace(ativado=True,razao="llm_indisponivel",motivo="mudanca_estado",texto=None)
        snap=SimpleNamespace(source_stimulus_id="s2",entity_id="x99",generated_at="2026-09-08T18:00:00+00:00",recent_changes=(),affective_state={})
        events=[]
        daemon=CognitiveDaemon(lambda:snap,lambda:{},BadLoop(),Publisher(),planner=ActionPlanner(),event_sink=lambda *x:events.append(x))
        daemon.run_once()
        self.assertFalse(any(x[0]=="plan_created" for x in events))
