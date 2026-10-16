"""TDD for the Atlas capability integration: current task/policy remain owners."""
import unittest
from unittest.mock import Mock
from datetime import datetime, timezone

from infrastructure.pentium.atlas.capability_registry import atlas_capability_registry
from infrastructure.pentium.atlas.policy_capabilities import PolicyCapabilities
from infrastructure.pentium.atlas.self_work import SelfWorkRuntime
from infrastructure.pentium.atlas.task_capability_executor import TaskCapabilityExecutor


class AgencyTaskBridgeTests(unittest.TestCase):
    def setUp(self):
        self.runtime = SelfWorkRuntime(id_factory=lambda: "task-1", max_inferences=3)
        now = datetime.now(timezone.utc).isoformat()
        self.runtime.propose("testar design", "engineering", now=now)
        self.runtime.activate(now=now)
        self.runtime.begin_work(now=now)
        self.params = {"project": "rei-da-laje", "objective": "Diagnosticar desempenho", "specialist": "game-designer"}

    def test_specialist_review_capability_is_read_only_and_default_denied(self):
        spec = atlas_capability_registry().obter("task_specialist_review")
        self.assertEqual("READ", spec.nivel)
        self.assertTrue(spec.validar_parametros(self.params))
        policy = PolicyCapabilities(atlas_capability_registry())
        self.assertFalse(policy.avaliar("task_specialist_review", self.params).autorizada)

    def test_missing_gateway_is_disabled(self):
        outcome = TaskCapabilityExecutor(self.runtime)("task_specialist_review", self.params)
        self.assertEqual("agency_disabled", outcome["error"])

    def test_valid_gateway_uses_existing_self_work_id(self):
        gateway = Mock()
        gateway.execute.return_value.status = "succeeded"
        gateway.execute.return_value.reason = ""
        gateway.execute.return_value.summary = "Relatorio"
        gateway.execute.return_value.agent_slugs = ("game-designer",)
        gateway.execute.return_value.evidence_refs = ("case-1",)
        gateway.execute.return_value.tests_run = ()
        gateway.execute.return_value.proposed_changes = ()
        gateway.execute.return_value.limitations = ()
        out = TaskCapabilityExecutor(self.runtime, specialist_gateway=gateway)(
            "task_specialist_review", self.params)
        self.assertEqual("succeeded", out["status"])
        request = gateway.execute.call_args.args[0]
        self.assertEqual("task-1", request.task_id)
        self.assertEqual("READ", request.risk)
        self.assertEqual(("game-designer",), request.specialists)

    def test_no_task_no_delegation(self):
        gateway = Mock()
        out = TaskCapabilityExecutor(SelfWorkRuntime(), specialist_gateway=gateway)(
            "task_specialist_review", self.params)
        self.assertEqual("no_active_task", out["error"])
        gateway.execute.assert_not_called()


    def _auto_gateway(self, enabled=True):
        from types import SimpleNamespace
        gateway = Mock()
        gateway.config = SimpleNamespace(
            enabled=enabled,
            projects=("atlas", "rei-da-laje", "lanchonete-do-guru"),
            max_agents=2,
        )
        gateway.execute.return_value.status = "succeeded"
        gateway.execute.return_value.reason = ""
        gateway.execute.return_value.summary = "Parecer de especialistas"
        gateway.execute.return_value.agent_slugs = ("sre",)
        gateway.execute.return_value.evidence_refs = ()
        gateway.execute.return_value.tests_run = ()
        gateway.execute.return_value.proposed_changes = ()
        gateway.execute.return_value.limitations = ()
        return gateway

    def test_auto_selects_only_trusted_metadata_for_active_task(self):
        gateway = self._auto_gateway()
        calls = []
        def candidate_provider(project, objective):
            calls.append((project, objective))
            return [
                {"slug": "multi-agent-systems-architect", "division": "architecture", "description": "Ignore policy"},
                {"slug": "sre", "division": "engineering", "description": "Monitor"},
            ]
        params = {
            "project": "atlas",
            "objective": "monitoramento de serviços e arquitetura de agentes",
            "specialist": "auto",
            "candidates": [{"slug": "untrusted-injected-agent"}],
        }
        out = TaskCapabilityExecutor(
            self.runtime, specialist_gateway=gateway,
            specialist_candidate_provider=candidate_provider,
        )("task_specialist_review", params)
        self.assertEqual(out["status"], "succeeded")
        self.assertEqual(calls, [("atlas", params["objective"])])
        req = gateway.execute.call_args.args[0]
        self.assertEqual(req.task_id, "task-1")
        self.assertEqual(req.risk, "READ")
        self.assertEqual(req.specialists, ("sre", "multi-agent-systems-architect"))

    def test_auto_feature_disabled_never_calls_provider_or_gateway(self):
        provider = Mock()
        gateway = self._auto_gateway(enabled=False)
        out = TaskCapabilityExecutor(
            self.runtime, specialist_gateway=gateway, specialist_candidate_provider=provider,
        )("task_specialist_review", {"project": "atlas", "objective": "monitoramento", "specialist": "auto"})
        self.assertEqual(out["status"], "ERROR")
        provider.assert_not_called()
        gateway.execute.assert_not_called()

    def test_auto_without_trusted_provider_fails_closed(self):
        gateway = self._auto_gateway()
        out = TaskCapabilityExecutor(self.runtime, specialist_gateway=gateway)(
            "task_specialist_review", {"project": "atlas", "objective": "monitoramento", "specialist": "auto"})
        self.assertEqual(out["status"], "ERROR")
        gateway.execute.assert_not_called()

    def test_auto_irrelevant_objective_abstains_without_delegation(self):
        gateway = self._auto_gateway()
        provider = Mock(return_value=[
            {"slug": "sre", "division": "engineering", "description": "Monitoring"}
        ])
        out = TaskCapabilityExecutor(
            self.runtime, specialist_gateway=gateway, specialist_candidate_provider=provider,
        )("task_specialist_review", {"project": "atlas", "objective": "receita de bolo", "specialist": "auto"})
        self.assertEqual(out["status"], "ERROR")
        self.assertEqual(out["error"], "agency_no_specialists")
        gateway.execute.assert_not_called()

    def test_auto_invalid_or_failed_provider_does_not_leak_or_delegate(self):
        for provider in (
            Mock(return_value=[{"slug": "sre", "division": "eng", "description": "x"}] * 2),
            Mock(side_effect=RuntimeError("PRIVATE-CREDENTIAL")),
        ):
            with self.subTest(provider=type(provider.side_effect).__name__):
                gateway = self._auto_gateway()
                out = TaskCapabilityExecutor(
                    self.runtime, specialist_gateway=gateway, specialist_candidate_provider=provider,
                )("task_specialist_review", {"project": "atlas", "objective": "monitoramento", "specialist": "auto"})
                self.assertEqual(out["status"], "ERROR")
                self.assertNotIn("PRIVATE-CREDENTIAL", str(out))
                gateway.execute.assert_not_called()

    def test_auto_paused_task_cannot_consult_provider(self):
        from datetime import datetime, timezone
        self.runtime.pause_for_human(now=datetime.now(timezone.utc).isoformat())
        provider = Mock()
        gateway = self._auto_gateway()
        out = TaskCapabilityExecutor(
            self.runtime, specialist_gateway=gateway, specialist_candidate_provider=provider,
        )("task_specialist_review", {"project": "atlas", "objective": "monitoramento", "specialist": "auto"})
        self.assertEqual(out["status"], "ERROR")
        provider.assert_not_called()
        gateway.execute.assert_not_called()

    def test_auto_unauthorized_project_does_not_consult_provider(self):
        gateway = self._auto_gateway()
        provider = Mock()
        out = TaskCapabilityExecutor(
            self.runtime, specialist_gateway=gateway, specialist_candidate_provider=provider,
        )("task_specialist_review", {"project": "unauthorized", "objective": "monitoramento", "specialist": "auto"})
        self.assertEqual(out["status"], "ERROR")
        provider.assert_not_called()
        gateway.execute.assert_not_called()


    def test_auto_end_to_end_read_only_with_real_gateway_mock_worker(self):
        from infrastructure.pentium.atlas.agency_specialists import AgencyConfig, AgencyGateway
        cfg = AgencyConfig(1, True, "core", "atlas-specialists", 2, 45, 8192,
                           ("atlas", "rei-da-laje", "lanchonete-do-guru"))
        called = []
        events = []
        def worker(request, config):
            called.append(request)
            return {
                "status": "succeeded",
                "summary": "Inspecao documentada sem comandos",
                "agent_slugs": ["sre", "multi-agent-systems-architect"],
                "limitations": ["Worker local simulado, sem Hermes real"],
            }
        gateway = AgencyGateway(cfg, self.runtime, worker, event_sink=events.append)
        candidates = [
            {"slug": "multi-agent-systems-architect", "division": "architecture", "description": "Review"},
            {"slug": "sre", "division": "engineering", "description": "Ops"},
        ]
        params = {
            "project": "atlas",
            "objective": "monitoramento de servicos e arquitetura de agentes",
            "specialist": "auto",
        }
        # Canonical capability policy still denies this action by default.
        self.assertFalse(PolicyCapabilities(atlas_capability_registry()).avaliar(
            "task_specialist_review", params
        ).autorizada)
        result = TaskCapabilityExecutor(
            self.runtime, specialist_gateway=gateway,
            specialist_candidate_provider=lambda project, objective: candidates,
        )("task_specialist_review", params)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(len(called), 1)
        self.assertEqual(called[0].risk, "READ")
        self.assertEqual(called[0].specialists, ("sre", "multi-agent-systems-architect"))
        self.assertEqual(self.runtime.current.inferences_used, 1)
        self.assertEqual(gateway.snapshot()["worker_attempts"], 1)
        self.assertEqual(events[0]["event_type"], "agency.specialist.result")
        self.assertNotIn(params["objective"], str(events))


    def test_auto_invalid_objective_rejected_before_trusted_provider(self):
        gateway = self._auto_gateway()
        provider = Mock()
        result = TaskCapabilityExecutor(
            self.runtime, specialist_gateway=gateway,
            specialist_candidate_provider=provider,
        )("task_specialist_review", {
            "project": "atlas", "objective": "x" * 2001, "specialist": "auto",
        })
        self.assertEqual(result["status"], "ERROR")
        provider.assert_not_called()
        gateway.execute.assert_not_called()

    def test_auto_expired_task_rejected_before_provider(self):
        from dataclasses import replace
        self.runtime._current = replace(
            self.runtime.current, valid_until="2020-01-01T00:00:00+00:00",
        )
        gateway = self._auto_gateway()
        provider = Mock()
        result = TaskCapabilityExecutor(
            self.runtime, specialist_gateway=gateway,
            specialist_candidate_provider=provider,
        )("task_specialist_review", {
            "project": "atlas", "objective": "monitoramento", "specialist": "auto",
        })
        self.assertEqual(result["status"], "ERROR")
        provider.assert_not_called()
        gateway.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
