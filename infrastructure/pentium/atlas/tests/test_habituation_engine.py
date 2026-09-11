import unittest

from infrastructure.pentium.atlas.continuous_intent import ContinuousIntent, IntentState, IntentType
from infrastructure.pentium.atlas.habituation_engine import HabituationEngine


def intent(state=IntentState.ATIVA):
    return ContinuousIntent(
        "intent-1", IntentType.ACOMPANHAR_RECUPERACAO, state,
        "core", "core", "degraded", .8,
        "2026-09-11T12:00:00+00:00", "2026-09-11T12:00:00+00:00",
        "2026-09-11T12:10:00+00:00",
    )


class HabituationEngineTests(unittest.TestCase):
    def test_first_message_allowed_and_equivalent_repeats_are_silent(self):
        engine = HabituationEngine(max_entries=8, ttl_s=300, clock=lambda: 10.0)
        first = engine.evaluate(intent(), "same")
        repeated = engine.evaluate(intent(), "same")
        self.assertTrue(first.allow_message)
        self.assertFalse(repeated.allow_message)
        self.assertTrue(repeated.tracking_visual)
        self.assertGreater(repeated.habituation, first.habituation)

    def test_material_change_allows_message_again(self):
        engine = HabituationEngine(max_entries=8, ttl_s=300, clock=lambda: 10.0)
        engine.evaluate(intent(), "v1")
        changed = engine.evaluate(intent(), "v2")
        self.assertTrue(changed.allow_message)

    def test_terminal_message_is_allowed_exactly_once(self):
        engine = HabituationEngine(max_entries=8, ttl_s=300, clock=lambda: 10.0)
        engine.evaluate(intent(), "v1")
        first = engine.evaluate(intent(IntentState.CONCLUIDA), "recovered", terminal=True)
        second = engine.evaluate(intent(IntentState.CONCLUIDA), "recovered", terminal=True)
        self.assertTrue(first.allow_message)
        self.assertFalse(second.allow_message)
        self.assertFalse(second.tracking_visual)

    def test_registry_is_bounded(self):
        now = [0.0]
        engine = HabituationEngine(max_entries=2, ttl_s=300, clock=lambda: now[0])
        for index in range(3):
            item = ContinuousIntent(
                f"i-{index}", IntentType.OBSERVAR, IntentState.ATIVA,
                f"s-{index}", f"e-{index}", "observe", .2,
                "2026-09-11T12:00:00+00:00", "2026-09-11T12:00:00+00:00",
                "2026-09-11T12:10:00+00:00",
            )
            engine.evaluate(item, "same")
            now[0] += 1.0
        self.assertLessEqual(engine.size, 2)


if __name__ == "__main__":
    unittest.main()
