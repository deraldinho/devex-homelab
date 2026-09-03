import unittest

from infrastructure.pentium.atlas.reaction_engine import ReactionEngine
from infrastructure.pentium.atlas.state_model import GlobalAssessment, TechnicalState


class FixedRng:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


class Clock:
    def __init__(self, value=100.0):
        self.value = value

    def __call__(self):
        return self.value


def assessment(state=TechnicalState.HEALTHY, intensity=0):
    return GlobalAssessment(None, state, intensity, ("test",), state == TechnicalState.RECOVERED)


class ReactionEngineTests(unittest.TestCase):
    def base_config(self):
        return {
            "mode": "normal",
            "anti_repeat_window": 2,
            "cooldowns": {"healthy": 10, "critical": 60},
            "memes_enabled": True,
            "reaction_pools": {
                "healthy": [
                    {"id": "healthy.a", "weight": 1},
                    {"id": "healthy.b", "weight": 3},
                ],
                "critical": [],
            },
            "meme_pools": {
                "healthy": [{"id": "meme.happy", "weight": 1}],
                "critical": [{"id": "meme.critical", "weight": 1}],
            },
        }

    def test_weighted_selection_is_deterministic_with_injected_rng(self):
        engine = ReactionEngine(self.base_config(), FixedRng(0.9), Clock())
        result = engine.decide(assessment(), ())
        self.assertEqual(result.reaction_id, "healthy.b")

    def test_recent_reaction_is_not_repeated_when_alternative_exists(self):
        engine = ReactionEngine(self.base_config(), FixedRng(0.0), Clock())
        result = engine.decide(assessment(), ("healthy.a",))
        self.assertEqual(result.reaction_id, "healthy.b")

    def test_cooldown_suppresses_noncritical_reaction(self):
        clock = Clock()
        engine = ReactionEngine(self.base_config(), FixedRng(0.0), clock)
        first = engine.decide(assessment(), ())
        second = engine.decide(assessment(), ())
        self.assertFalse(first.suppressed)
        self.assertTrue(second.suppressed)

    def test_empty_noncritical_pool_returns_explicit_silence(self):
        config = self.base_config()
        config["reaction_pools"]["healthy"] = []
        engine = ReactionEngine(config, FixedRng(0.0), Clock())
        result = engine.decide(assessment(), ())
        self.assertTrue(result.suppressed)
        self.assertIsNone(result.reaction_id)

    def test_memes_can_be_disabled(self):
        config = self.base_config()
        config["memes_enabled"] = False
        engine = ReactionEngine(config, FixedRng(0.0), Clock())
        result = engine.decide(assessment(), ())
        self.assertIsNone(result.meme_id)

    def test_critical_always_emits_canonical_reaction_and_meme_is_secondary(self):
        engine = ReactionEngine(self.base_config(), FixedRng(0.0), Clock())
        result = engine.decide(assessment(TechnicalState.CRITICAL, 4), ("critical.canonical",))
        self.assertFalse(result.suppressed)
        self.assertEqual(result.category, "critical")
        self.assertEqual(result.reaction_id, "critical.canonical")
        self.assertEqual(result.meme_id, "meme.critical")


if __name__ == "__main__":
    unittest.main()
