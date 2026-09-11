import unittest
from types import SimpleNamespace

from infrastructure.pentium.atlas.behavior_selector import BehaviorDecision
from infrastructure.pentium.atlas.continuous_intent import IntentState, IntentType
from infrastructure.pentium.atlas.continuous_intent_machine import ContinuousIntentMachine


def decision(tipo=IntentType.ACOMPANHAR_RECUPERACAO, assunto="core", prioridade=.8, motivo="degraded"):
    return BehaviorDecision(tipo, assunto, assunto, motivo, prioridade, prioridade)


def snapshot(*, recovered=False):
    return SimpleNamespace(
        focus={"principal": {"assunto_id": "core", "entidade_id": "core", "recuperado": recovered}},
        entity_id="core",
    )


class ContinuousIntentMachineTests(unittest.TestCase):
    def machine(self, ttl_s=300):
        ids = iter(("intent-1", "intent-2", "intent-3"))
        return ContinuousIntentMachine(ttl_s=ttl_s, activation_threshold=.5, id_factory=lambda: next(ids))

    def test_candidate_activates_for_stable_recovery_tracking(self):
        machine = self.machine()
        transition = machine.update(decision(), snapshot(), now="2026-09-11T12:00:00+00:00")
        self.assertEqual(IntentState.ATIVA, transition.intent.estado)
        self.assertEqual("intent-1", transition.intent.intencao_id)
        self.assertTrue(transition.changed)

    def test_human_preempts_then_same_subject_resumes(self):
        machine = self.machine()
        machine.update(decision(), snapshot(), now="2026-09-11T12:00:00+00:00")
        waiting = machine.update(
            decision(IntentType.INTERAGIR_COM_HUMANO, prioridade=1.0, motivo="interacao_humana"),
            snapshot(), now="2026-09-11T12:01:00+00:00", human_interaction=True,
        )
        self.assertEqual(IntentState.AGUARDANDO, waiting.intent.estado)
        resumed = machine.update(decision(), snapshot(), now="2026-09-11T12:02:00+00:00")
        self.assertEqual(IntentState.ATIVA, resumed.intent.estado)
        self.assertEqual("intent-1", resumed.intent.intencao_id)

    def test_recovery_completes_current_intent_once(self):
        machine = self.machine()
        machine.update(decision(), snapshot(), now="2026-09-11T12:00:00+00:00")
        completed = machine.update(
            decision(IntentType.ENCERRAR_ACOMPANHAMENTO, prioridade=.95, motivo="recuperacao"),
            snapshot(recovered=True), now="2026-09-11T12:03:00+00:00",
        )
        self.assertEqual(IntentState.CONCLUIDA, completed.intent.estado)
        self.assertTrue(completed.intent.terminal)
        repeated = machine.update(
            decision(IntentType.ENCERRAR_ACOMPANHAMENTO, prioridade=.95, motivo="recuperacao"),
            snapshot(recovered=True), now="2026-09-11T12:04:00+00:00",
        )
        self.assertIsNone(repeated.intent)

    def test_semantic_conflict_cancels_before_new_subject(self):
        machine = self.machine()
        machine.update(decision(), snapshot(), now="2026-09-11T12:00:00+00:00")
        conflict = machine.update(decision(assunto="x99"), snapshot(), now="2026-09-11T12:01:00+00:00")
        self.assertEqual(IntentState.CANCELADA, conflict.intent.estado)

    def test_ttl_expires_non_terminal_intent(self):
        machine = self.machine(ttl_s=10)
        machine.update(decision(), snapshot(), now="2026-09-11T12:00:00+00:00")
        expired = machine.update(decision(), snapshot(), now="2026-09-11T12:00:11+00:00")
        self.assertEqual(IntentState.EXPIRADA, expired.intent.estado)


if __name__ == "__main__":
    unittest.main()
