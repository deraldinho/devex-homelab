import unittest
from types import SimpleNamespace

from infrastructure.pentium.atlas.behavior_selector import BehaviorSelector
from infrastructure.pentium.atlas.cognitive_daemon import CognitiveDaemon
from infrastructure.pentium.atlas.continuous_intent import IntentState
from infrastructure.pentium.atlas.continuous_intent_machine import ContinuousIntentMachine
from infrastructure.pentium.atlas.habituation_engine import HabituationEngine


def snapshot(index, *, recovered=False):
    return SimpleNamespace(
        source_stimulus_id=f"s{index}",
        generated_at=f"2026-09-11T12:00:{index:02d}+00:00",
        entity_id="core", recent_changes=(), affective_state={"estresse": .1},
        perception={"confianca": .9, "estado": "observado"},
        incident=None if recovered else {"estado_recuperacao": "aberto"},
        focus={"principal": {
            "assunto_id": "core", "entidade_id": "core",
            "gravidade": .1 if recovered else .8,
            "impacto_afetivo": .4, "importancia": .8, "novidade": .6,
            "urgencia": .7, "recencia": 1.0, "critico": False,
            "recuperado": recovered,
        }},
    )


class FakeLoop:
    def processar(self, **kwargs):
        return SimpleNamespace(
            ativado=True, motivo="mudanca_estado", texto="acompanho core",
            razao=None, backend="fake", duracao_ms=1, resumo="core",
            intencao=None, parametros_intencao=None, confianca=.8,
            requer_confirmacao=False, intencao_autorizada=False,
            solicitar_fala=False,
        )


class FakeObservable:
    def publish(self, *args): pass
    def publish_phase(self, *args, **kwargs): pass


class Recorder:
    def __init__(self): self.items=[]
    def publish(self, intent, *, communication_mode, material_fingerprint):
        self.items.append((intent, communication_mode, material_fingerprint))


class ContinuousBehaviorReplayTests(unittest.TestCase):
    def build_daemon(self, snapshots):
        queue=list(snapshots); recorder=Recorder(); machine=ContinuousIntentMachine(
            ttl_s=300, activation_threshold=.5, id_factory=lambda:"intent-core",
        )
        daemon=CognitiveDaemon(
            lambda: queue.pop(0), lambda: {}, FakeLoop(), FakeObservable(),
            behavior_selector=BehaviorSelector(), intent_machine=machine,
            habituation_engine=HabituationEngine(max_entries=8, ttl_s=300, clock=lambda:10.0),
            intent_publisher=recorder,
        )
        return daemon, recorder, machine

    def test_ten_cycle_replay_preserves_one_intent_and_two_autonomous_messages(self):
        sequence=[
            snapshot(1), snapshot(2), snapshot(3), snapshot(4), snapshot(5), snapshot(6),
            snapshot(7), snapshot(8), snapshot(9, recovered=True), snapshot(10, recovered=True),
        ]
        daemon, recorder, machine = self.build_daemon(sequence)
        for cycle in range(1, 11):
            if cycle == 7:
                envelope=SimpleNamespace(
                    message_id="m1", stimulus_id="human-1", channel="dashboard",
                    actor_id=None, conversation_id=None, reply_target=None,
                    message="oi atlas", created_at="2026-09-11T12:00:07+00:00",
                )
                daemon._chat_inbox=SimpleNamespace(claim_next=lambda:envelope, ack=lambda _id:None)
            elif cycle == 8:
                daemon._chat_inbox=None
            daemon.run_once()

        states=[item[0].estado if item[0] is not None else None for item in recorder.items]
        modes=[item[1] for item in recorder.items]
        self.assertEqual(IntentState.ATIVA, states[0])
        self.assertEqual(["silent_tracking"] * 5, modes[1:6])
        self.assertEqual(IntentState.AGUARDANDO, states[6])
        self.assertEqual(IntentState.ATIVA, states[7])
        self.assertEqual(IntentState.CONCLUIDA, states[8])
        self.assertIsNone(states[9])
        autonomous_messages=sum(
            1 for state, mode in zip(states, modes)
            if mode in {"normal", "terminal"} and state is not IntentState.AGUARDANDO and state is not None
        )
        self.assertEqual(2, autonomous_messages)
        self.assertIsNone(machine.current)

    def test_restart_on_already_recovered_snapshot_does_not_revive_old_intent(self):
        daemon, recorder, machine = self.build_daemon((snapshot(1, recovered=True),))
        daemon.run_once()
        self.assertEqual(1, len(recorder.items))
        self.assertIsNone(recorder.items[0][0])
        self.assertIsNone(machine.current)


if __name__ == "__main__": unittest.main()
