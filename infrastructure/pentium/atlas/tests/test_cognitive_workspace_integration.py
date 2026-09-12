import unittest
from types import SimpleNamespace

from infrastructure.pentium.atlas.cognitive_daemon import CognitiveDaemon
from infrastructure.pentium.atlas.cognitive_router import CognitiveRouter
from infrastructure.pentium.atlas.token_budget_governor import TokenBudgetGovernor
from infrastructure.pentium.atlas.self_work import SelfWorkRuntime, SelfWorkState


class FakeLoop:
    def __init__(self): self.calls=[]
    def processar(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(ativado=True, razao=None, texto="ok", motivo="x")

class Pub:
    def publish(self,*args): pass
    def publish_phase(self,*args,**kwargs): pass

def snap(stimulus, *, candidate=False):
    return SimpleNamespace(
        source_stimulus_id=stimulus, generated_at="2026-09-12T18:00:00+00:00",
        entity_id="atlas", recent_changes=(), affective_state={}, incident=None,
        perception={"confianca":.9},
        focus={"principal":{"assunto_id":"workspace:notes","entidade_id":"atlas",
            "self_work_candidate":candidate,"gravidade":0,"importancia":.8,"urgencia":.1,
            "novidade":.8,"recencia":1,"impacto_afetivo":.1,"critico":False,"recuperado":False}},
    )

class CognitiveWorkspaceIntegrationTests(unittest.TestCase):
    def test_materialmente_igual_sem_deadline_evita_segunda_inferencia(self):
        queue=[snap("s1"),snap("s2")]; loop=FakeLoop()
        router=CognitiveRouter(TokenBudgetGovernor(window_budget=10000))
        daemon=CognitiveDaemon(lambda:queue.pop(0),lambda:{},loop,Pub(),cognitive_router=router)
        daemon.run_once(); second=daemon.run_once()
        self.assertEqual(1,len(loop.calls))
        self.assertIsNone(second)

    def test_human_preempts_self_work_and_resumes_after_ack(self):
        runtime=SelfWorkRuntime(id_factory=lambda:"sw-1")
        runtime.propose("organizar notas","notes",now="2026-09-12T18:00:00+00:00")
        runtime.activate(now="2026-09-12T18:00:01+00:00")
        runtime.begin_work(now="2026-09-12T18:00:02+00:00")
        loop=FakeLoop(); base=snap("s1")
        envelope=SimpleNamespace(message_id="m1",stimulus_id="human-1",channel="dashboard",
            actor_id=None,conversation_id=None,reply_target=None,message="oi",
            created_at="2026-09-12T18:00:03+00:00")
        inbox=SimpleNamespace(claim_next=lambda:envelope,ack=lambda _id:None)
        daemon=CognitiveDaemon(lambda:base,lambda:{},loop,Pub(),chat_inbox=inbox,self_work_runtime=runtime)
        daemon.run_once()
        self.assertIsNotNone(runtime.current)
        self.assertEqual(SelfWorkState.WORKING,runtime.current.state)
        self.assertEqual("",runtime.current.reason)

    def test_self_work_candidate_is_started_bounded_without_extra_privilege(self):
        from infrastructure.pentium.atlas.behavior_selector import BehaviorSelector
        from infrastructure.pentium.atlas.continuous_intent_machine import ContinuousIntentMachine
        from infrastructure.pentium.atlas.habituation_engine import HabituationEngine
        runtime=SelfWorkRuntime(id_factory=lambda:"sw-1")
        loop=FakeLoop(); base=snap("s1",candidate=True)
        daemon=CognitiveDaemon(lambda:base,lambda:{},loop,Pub(),
            behavior_selector=BehaviorSelector(),intent_machine=ContinuousIntentMachine(activation_threshold=.2,id_factory=lambda:"i1"),
            habituation_engine=HabituationEngine(clock=lambda:10.0),self_work_runtime=runtime)
        daemon.run_once()
        self.assertIsNotNone(runtime.current)
        self.assertIn(runtime.current.state,{SelfWorkState.ACTIVE,SelfWorkState.WORKING})
        self.assertEqual("notes",runtime.current.area)


if __name__ == "__main__": unittest.main()
