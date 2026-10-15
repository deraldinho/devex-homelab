"""Deterministic security and ranking tests for the Atlas zero-cost model selector."""
import unittest
from infrastructure.pentium.atlas.free_model_selection import ModelOffer, select_free_models


class FreeModelSelectionTests(unittest.TestCase):
    def offer(self, name, *, price=0, verified=True, tasks=frozenset({"code"}), quality=5,
              latency=100, quota=True, cooldown=False):
        return ModelOffer("opencode", name, price, price, verified, tasks, quality, latency, quota, cooldown)

    def test_selects_high_quality_before_latency_at_equal_zero_cost(self):
        models = (self.offer("fast", quality=7), self.offer("best", quality=9, latency=500))
        result = select_free_models(models, task="code",
                                    authorized=frozenset({("opencode", "fast"), ("opencode", "best")}))
        self.assertEqual([m.model for m in result], ["best", "fast"])

    def test_rejects_unknown_and_paid_prices(self):
        models = (self.offer("unknown", price=None), self.offer("paid", price=0.01))
        self.assertEqual(select_free_models(models, task="code",
                         authorized=frozenset({("opencode", "unknown"), ("opencode", "paid")})), ())

    def test_authorization_and_entitlement_are_both_required(self):
        self.assertEqual(select_free_models((self.offer("free", verified=False),), task="code",
                         authorized=frozenset({("opencode", "free")})), ())
        self.assertEqual(select_free_models((self.offer("free"),), task="code", authorized=frozenset()), ())

    def test_cooldown_quota_and_task_limits(self):
        models = (self.offer("quota", quota=False), self.offer("cooldown", cooldown=True),
                  self.offer("vision", tasks=frozenset({"vision"})))
        self.assertEqual(select_free_models(models, task="code",
                         authorized=frozenset({("opencode", m.model) for m in models})), ())

    def test_deduplicates_provider_and_model(self):
        model = self.offer("one")
        self.assertEqual(len(select_free_models((model, model), task="code",
                                      authorized=frozenset({("opencode", "one")}))), 1)


if __name__ == "__main__":
    unittest.main()
