import unittest

from infrastructure.pentium.atlas.token_budget_governor import TokenBudgetGovernor, TokenBudgetMode


class TokenBudgetGovernorTests(unittest.TestCase):
    def test_modos_aumentam_com_pressao(self):
        governor = TokenBudgetGovernor(window_budget=1000)
        self.assertEqual(TokenBudgetMode.NORMAL, governor.mode)
        governor.record(750)
        self.assertEqual(TokenBudgetMode.CONSERVATIVE, governor.mode)
        governor.record(120)
        self.assertEqual(TokenBudgetMode.RESTRICTED, governor.mode)
        governor.record(100)
        self.assertEqual(TokenBudgetMode.HUMAN_ONLY, governor.mode)

    def test_human_e_incident_preservam_prioridade(self):
        governor = TokenBudgetGovernor(window_budget=100)
        governor.record(100)
        self.assertTrue(governor.allow("human"))
        self.assertTrue(governor.allow("incident"))
        self.assertFalse(governor.allow("self_work"))
        self.assertFalse(governor.allow("reflection"))

    def test_self_work_reduz_antes_de_human(self):
        governor = TokenBudgetGovernor(window_budget=1000)
        governor.record(880)
        self.assertEqual(TokenBudgetMode.RESTRICTED, governor.mode)
        self.assertFalse(governor.allow("self_work"))
        self.assertTrue(governor.allow("human"))

    def test_metricas_contabilizam_tokens(self):
        governor = TokenBudgetGovernor(window_budget=1000)
        governor.record(120, category="human")
        governor.record(30, category="self_work")
        metrics = governor.metrics()
        self.assertEqual(150, metrics["tokens_used"])
        self.assertEqual(120, metrics["by_category"]["human"])
