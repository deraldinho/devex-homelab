import unittest

from infrastructure.pentium.atlas.capability_registry import atlas_capability_registry
from infrastructure.pentium.atlas.policy_capabilities import PolicyCapabilities


class AutonomyPolicyV1Tests(unittest.TestCase):
    def setUp(self):
        self.policy = PolicyCapabilities(
            atlas_capability_registry(),
            read_auto_allow=("get_host_status",),
            control_allow=(),
            auto_control_allow=("restart_service",),
            auto_hosts=("pentium",),
            auto_services=("atlas-observation.service", "atlas-dashboard.service"),
        )

    def test_safe_internal_restart_is_auto(self):
        decision = self.policy.avaliar("restart_service", {
            "host": "pentium", "service": "atlas-observation.service"})
        self.assertTrue(decision.autorizada)
        self.assertFalse(decision.requer_confirmacao)
        self.assertEqual("AUTO", decision.autonomia)

    def test_control_outside_safe_scope_requires_confirmation(self):
        decision = self.policy.avaliar("restart_service", {
            "host": "core", "service": "docker.service"})
        self.assertFalse(decision.autorizada)
        self.assertTrue(decision.requer_confirmacao)
        self.assertEqual("CONFIRM", decision.autonomia)

    def test_destructive_action_is_never_auto(self):
        decision = self.policy.avaliar("reboot_host", {"host": "pentium"})
        self.assertFalse(decision.autorizada)
        self.assertTrue(decision.requer_confirmacao)
        self.assertEqual("CONFIRM", decision.autonomia)

    def test_unknown_capability_is_denied(self):
        decision = self.policy.avaliar("shell", {})
        self.assertFalse(decision.autorizada)
        self.assertFalse(decision.requer_confirmacao)
        self.assertEqual("DENY", decision.autonomia)

    def test_cooldown_blocks_rapid_second_restart(self):
        current_time = 1000.0
        policy = PolicyCapabilities(
            atlas_capability_registry(),
            auto_control_allow=("restart_service",),
            auto_hosts=("pentium",),
            auto_services=("atlas-observation.service",),
            cooldown_s=300.0,
            clock=lambda: current_time,
        )
        params = {"host": "pentium", "service": "atlas-observation.service"}
        decision1 = policy.avaliar("restart_service", params)
        self.assertEqual("AUTO", decision1.autonomia)
        policy.registrar_execucao("restart_service", params)

        # 60s later: still in cooldown
        current_time += 60.0
        decision2 = policy.avaliar("restart_service", params)
        self.assertFalse(decision2.autorizada)
        self.assertTrue(decision2.requer_confirmacao)
        self.assertEqual("CONFIRM", decision2.autonomia)
        self.assertEqual("cooldown_active", decision2.razao)

        # 301s later (after 300s total cooldown): allowed again
        current_time += 241.0
        decision3 = policy.avaliar("restart_service", params)
        self.assertTrue(decision3.autorizada)
        self.assertEqual("AUTO", decision3.autonomia)

    def test_budget_blocks_after_max_restarts_in_window(self):
        current_time = 10000.0
        policy = PolicyCapabilities(
            atlas_capability_registry(),
            auto_control_allow=("restart_service",),
            auto_hosts=("pentium",),
            auto_services=("atlas-observation.service",),
            cooldown_s=60.0,
            max_auto_per_window=2,
            window_s=3600.0,
            clock=lambda: current_time,
        )
        params = {"host": "pentium", "service": "atlas-observation.service"}

        # 1st restart
        self.assertEqual("AUTO", policy.avaliar("restart_service", params).autonomia)
        policy.registrar_execucao("restart_service", params)

        # 2nd restart after cooldown
        current_time += 100.0
        self.assertEqual("AUTO", policy.avaliar("restart_service", params).autonomia)
        policy.registrar_execucao("restart_service", params)

        # 3rd restart after cooldown, but within 1-hour window (budget exhausted)
        current_time += 100.0
        decision3 = policy.avaliar("restart_service", params)
        self.assertFalse(decision3.autorizada)
        self.assertTrue(decision3.requer_confirmacao)
        self.assertEqual("CONFIRM", decision3.autonomia)
        self.assertEqual("action_budget_exceeded", decision3.razao)

        # 1 hour after first restart (window slides)
        current_time += 3500.0
        decision4 = policy.avaliar("restart_service", params)
        self.assertTrue(decision4.autorizada)
        self.assertEqual("AUTO", decision4.autonomia)


if __name__ == "__main__":
    unittest.main()
