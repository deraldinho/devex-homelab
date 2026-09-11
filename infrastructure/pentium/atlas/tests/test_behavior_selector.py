import unittest
from types import SimpleNamespace

from infrastructure.pentium.atlas.behavior_selector import BehaviorSelector
from infrastructure.pentium.atlas.continuous_intent import IntentType


def snapshot(*, recovered=False, critical=False, severity=.8, confidence=.8):
    return SimpleNamespace(
        focus={"principal": {
            "assunto_id": "core", "entidade_id": "core", "gravidade": severity,
            "impacto_afetivo": .4, "importancia": .8, "novidade": .6,
            "urgencia": .7, "recencia": 1.0, "critico": critical,
            "recuperado": recovered,
        }},
        perception={"confianca": confidence, "estado": "observado"},
        incident=None if recovered else {"estado_recuperacao": "aberto"},
        affective_state={"estresse": .2, "engajamento": .5},
    )


class BehaviorSelectorTests(unittest.TestCase):
    def test_human_interaction_always_preempts_passive_behavior(self):
        decision = BehaviorSelector().select(snapshot(), human_interaction=True, habituation=0.0)
        self.assertEqual(IntentType.INTERAGIR_COM_HUMANO, decision.tipo)
        self.assertGreaterEqual(decision.prioridade, .99)

    def test_degraded_focus_selects_recovery_tracking(self):
        decision = BehaviorSelector().select(snapshot(), human_interaction=False, habituation=0.0)
        self.assertEqual(IntentType.ACOMPANHAR_RECUPERACAO, decision.tipo)
        self.assertEqual("core", decision.assunto_id)
        self.assertGreater(decision.utility, .5)

    def test_recovered_focus_selects_terminal_behavior(self):
        decision = BehaviorSelector().select(snapshot(recovered=True, severity=.1), human_interaction=False, habituation=.7)
        self.assertEqual(IntentType.ENCERRAR_ACOMPANHAMENTO, decision.tipo)
        self.assertEqual("core", decision.entidade_id)

    def test_habituation_reduces_utility_but_never_below_zero(self):
        selector = BehaviorSelector()
        fresh = selector.select(snapshot(), human_interaction=False, habituation=0.0)
        repeated = selector.select(snapshot(), human_interaction=False, habituation=1.0)
        self.assertLess(repeated.utility, fresh.utility)
        self.assertGreaterEqual(repeated.utility, 0.0)


if __name__ == "__main__":
    unittest.main()
