import unittest

from infrastructure.pentium.atlas.continuous_intent import (
    ContinuousIntent, IntentState, IntentType,
)


class ContinuousIntentModelTests(unittest.TestCase):
    def test_intent_normalizes_identity_and_exposes_terminal_state(self):
        intent = ContinuousIntent(
            intencao_id=" i-1 ", tipo=IntentType.ACOMPANHAR_RECUPERACAO,
            estado=IntentState.ATIVA, assunto_id=" core ", entidade_id=" core ",
            motivo="degraded", prioridade=.8,
            iniciado_em="2026-09-11T12:00:00+00:00",
            atualizado_em="2026-09-11T12:00:00+00:00",
            valido_ate="2026-09-11T12:10:00+00:00",
        )
        self.assertEqual("i-1", intent.intencao_id)
        self.assertEqual("core", intent.assunto_id)
        self.assertFalse(intent.terminal)

    def test_terminal_states_are_explicit(self):
        base = dict(
            intencao_id="i-1", tipo=IntentType.OBSERVAR, assunto_id="x99",
            entidade_id="x99", motivo="observe", prioridade=.2,
            iniciado_em="2026-09-11T12:00:00+00:00",
            atualizado_em="2026-09-11T12:00:00+00:00",
            valido_ate="2026-09-11T12:10:00+00:00",
        )
        for state in (IntentState.CONCLUIDA, IntentState.CANCELADA, IntentState.EXPIRADA):
            self.assertTrue(ContinuousIntent(estado=state, **base).terminal)

    def test_invalid_priority_and_naive_timestamps_are_rejected(self):
        with self.assertRaises(ValueError):
            ContinuousIntent(
                "i", IntentType.OBSERVAR, IntentState.ATIVA, "x", "x", "m", 1.1,
                "2026-09-11T12:00:00+00:00", "2026-09-11T12:00:00+00:00",
                "2026-09-11T12:10:00+00:00",
            )
        with self.assertRaises(ValueError):
            ContinuousIntent(
                "i", IntentType.OBSERVAR, IntentState.ATIVA, "x", "x", "m", .2,
                "2026-09-11T12:00:00", "2026-09-11T12:00:00+00:00",
                "2026-09-11T12:10:00+00:00",
            )
