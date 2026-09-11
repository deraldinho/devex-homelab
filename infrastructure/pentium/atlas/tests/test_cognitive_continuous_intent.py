import unittest
from types import SimpleNamespace

from infrastructure.pentium.atlas.behavior_selector import BehaviorSelector
from infrastructure.pentium.atlas.cognitive_daemon import CognitiveDaemon
from infrastructure.pentium.atlas.continuous_intent import IntentState
from infrastructure.pentium.atlas.continuous_intent_machine import ContinuousIntentMachine
from infrastructure.pentium.atlas.habituation_engine import HabituationEngine


def snapshot(stimulus_id, *, recovered=False):
    return SimpleNamespace(
        source_stimulus_id=stimulus_id,
        generated_at=f"2026-09-11T12:00:{int(stimulus_id[1:]):02d}+00:00",
        entity_id="core", recent_changes=(), affective_state={"estresse": .1},
        perception={"confianca": .9, "estado": "observado"},
        incident=None if recovered else {"estado_recuperacao": "aberto"},
        focus={"principal": {
            "assunto_id": "core", "entidade_id": "core", "gravidade": .8 if not recovered else .1,
            "impacto_afetivo": .4, "importancia": .8, "novidade": .6,
            "urgencia": .7, "recencia": 1.0, "critico": False, "recuperado": recovered,
        }},
    )


class FakeLoop:
    def __init__(self): self.calls=[]
    def processar(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            ativado=True, motivo="mudanca_estado", texto="acompanho core",
            razao=None, backend="fake", duracao_ms=1, resumo="core",
            intencao=None, parametros_intencao=None, confianca=.8,
            requer_confirmacao=False, intencao_autorizada=False, solicitar_fala=False,
        )


class FakeObservable:
    def publish(self, *args): pass
    def publish_phase(self, *args, **kwargs): pass


class FakeIntentPublisher:
    def __init__(self): self.items=[]
    def publish(self, intent, *, communication_mode, material_fingerprint):
        self.items.append((intent, communication_mode, material_fingerprint))


class CognitiveContinuousIntentTests(unittest.TestCase):
    def daemon(self, snapshots):
        queue=list(snapshots); loop=FakeLoop(); published=FakeIntentPublisher()
        daemon=CognitiveDaemon(
            lambda: queue.pop(0), lambda: {}, loop, FakeObservable(),
            behavior_selector=BehaviorSelector(),
            intent_machine=ContinuousIntentMachine(
                ttl_s=300, activation_threshold=.5, id_factory=lambda:"intent-1",
            ),
            habituation_engine=HabituationEngine(max_entries=8, ttl_s=300, clock=lambda:10.0),
            intent_publisher=published,
        )
        return daemon, loop, published

    def test_first_detection_then_equivalent_cycle_becomes_silent_tracking(self):
        daemon, loop, published = self.daemon((snapshot("s1"), snapshot("s2")))
        daemon.run_once(); daemon.run_once()
        self.assertEqual(IntentState.ATIVA, published.items[0][0].estado)
        self.assertEqual("normal", published.items[0][1])
        self.assertEqual(IntentState.ATIVA, published.items[1][0].estado)
        self.assertEqual("silent_tracking", published.items[1][1])
        self.assertEqual(2, len(loop.calls))

    def test_human_interaction_preempts_and_next_observation_resumes(self):
        base = snapshot("s1")
        snapshots=[base, base, snapshot("s2")]
        daemon, loop, published = self.daemon(snapshots)
        daemon.run_once()
        envelope=SimpleNamespace(
            message_id="m1", stimulus_id="human-1", channel="dashboard", actor_id=None,
            conversation_id=None, reply_target=None, message="oi atlas",
            created_at="2026-09-11T12:00:10+00:00",
        )
        daemon._chat_inbox=SimpleNamespace(
            claim_next=lambda: envelope, ack=lambda _id: None,
        )
        daemon.run_once()
        daemon._chat_inbox=None
        daemon.run_once()
        states=[item[0].estado for item in published.items]
        self.assertEqual([IntentState.ATIVA, IntentState.AGUARDANDO, IntentState.ATIVA], states)

    def test_recovery_publishes_single_terminal_intent(self):
        daemon, loop, published = self.daemon((snapshot("s1"), snapshot("s2", recovered=True), snapshot("s3", recovered=True)))
        daemon.run_once(); daemon.run_once(); daemon.run_once()
        terminals=[item for item in published.items if item[0] is not None and item[0].terminal]
        self.assertEqual(1, len(terminals))
        self.assertEqual(IntentState.CONCLUIDA, terminals[0][0].estado)
        self.assertEqual("terminal", terminals[0][1])


if __name__ == "__main__":
    unittest.main()


class CognitiveContinuousIntentFallbackTests(unittest.TestCase):
    def test_selector_failure_falls_back_to_existing_cognitive_flow(self):
        loop=FakeLoop(); events=[]
        class BrokenSelector:
            def select(self,*args,**kwargs): raise RuntimeError("selector")
        daemon=CognitiveDaemon(
            lambda:snapshot("s1"), lambda:{}, loop, FakeObservable(),
            behavior_selector=BrokenSelector(),
            intent_machine=ContinuousIntentMachine(id_factory=lambda:"i1"),
            habituation_engine=HabituationEngine(clock=lambda:10.0),
            event_sink=lambda kind,payload:events.append((kind,payload)),
        )
        response=daemon.run_once()
        self.assertTrue(response.ativado)
        self.assertEqual(1,len(loop.calls))
        self.assertEqual("continuous_intent_error",events[0][0])
