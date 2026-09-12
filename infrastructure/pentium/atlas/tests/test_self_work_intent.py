import unittest
from types import SimpleNamespace

from infrastructure.pentium.atlas.behavior_selector import BehaviorSelector
from infrastructure.pentium.atlas.continuous_intent import IntentType, IntentState
from infrastructure.pentium.atlas.continuous_intent_machine import ContinuousIntentMachine


class SelfWorkIntentTests(unittest.TestCase):
    def snapshot(self, *, candidate=True):
        return SimpleNamespace(
            focus={"principal": {
                "assunto_id": "workspace:notes",
                "entidade_id": "atlas-workspace",
                "self_work_candidate": candidate,
                "gravidade": 0.0, "importancia": .7, "urgencia": .1,
                "novidade": .8, "recencia": 1.0, "impacto_afetivo": .2,
                "critico": False, "recuperado": False,
            }},
            perception={"confianca": .9}, incident=None,
            affective_state={"estresse": .1}, entity_id="atlas-workspace",
        )

    def test_selector_emite_self_work_somente_quando_candidato_explicito(self):
        selector = BehaviorSelector()
        decision = selector.select(self.snapshot(), human_interaction=False, habituation=0.0)
        self.assertEqual(IntentType.SELF_WORK, decision.tipo)
        normal = selector.select(self.snapshot(candidate=False), human_interaction=False, habituation=0.0)
        self.assertNotEqual(IntentType.SELF_WORK, normal.tipo)

    def test_continuous_intent_pode_acompanhar_self_work_sem_executa_lo(self):
        selector = BehaviorSelector()
        decision = selector.select(self.snapshot(), human_interaction=False, habituation=0.0)
        machine = ContinuousIntentMachine(activation_threshold=.2, id_factory=lambda: "intent-self")
        transition = machine.update(decision, self.snapshot(), now="2026-09-12T18:00:00+00:00")
        self.assertEqual(IntentType.SELF_WORK, transition.intent.tipo)
        self.assertEqual(IntentState.ATIVA, transition.intent.estado)


if __name__ == "__main__":
    unittest.main()
