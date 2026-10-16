"""LOCAL E2E certification TDD (read-only, no production operations).
CP-AA6: Simulated end-to-end agency specialist review using actual SelfWorkRuntime
and AgencyGateway with injected trusted candidate provider and FAKE READ-only worker.

IMPORTANT: This is LOCAL SIMULATION ONLY. Physical CP-AA6 certification is BLOCKED due to:
- Core and Pentium SSH authenticated read-only inventory succeeded on 2026-10-13,
  but typed worker transport and real Hermes subagent execution are unverified
- P0 Backup/DR restore proof remains unverified
- This test suite performs no real Hermes calls, SSH, or production operations.

Each test is independent, deterministic, OFFLINE, and uses only in-memory objects.
No temporary files, no config changes, no service restarts.
"""
import unittest
from datetime import datetime, timezone
from typing import Any, Mapping
from unittest.mock import Mock

from infrastructure.pentium.atlas.agency_specialists import (
    AgencyConfig, AgencyRequest, AgencyGateway, AgencyResult,
)
from infrastructure.pentium.atlas.agency_specialist_selector import select_specialists
from infrastructure.pentium.atlas.capability_registry import atlas_capability_registry
from infrastructure.pentium.atlas.policy_capabilities import PolicyCapabilities
from infrastructure.pentium.atlas.self_work import SelfWorkRuntime, SelfWorkState
from infrastructure.pentium.atlas.task_capability_executor import TaskCapabilityExecutor


# Trusted candidate provider for each project (in-memory, bounded metadata)
# Uses canonical slugs from pinned catalog (msitarzewski/agency-agents@f99f6aa)
def trusted_candidate_provider(project: str, objective: str) -> list[dict[str, str]]:
    """Trusted, bounded candidate metadata source. No external I/O, no secrets."""
    if project == "atlas":
        return [
            {"slug": "sre-site-reliability-engineer", "division": "platform", "description": "Monitoring, observability, service health"},
            {"slug": "multi-agent-systems-architect", "division": "architecture", "description": "Agent orchestration, architecture review"},
        ]
    if project == "rei-da-laje":
        return [
            {"slug": "game-designer", "division": "gameplay", "description": "Pipa combat design, game mechanics"},
            {"slug": "performance-benchmarker", "division": "performance", "description": "FPS benchmarking, performance profiling"},
        ]
    if project == "lanchonete-do-guru":
        return [
            {"slug": "backend-architect", "division": "backend", "description": "API design, server, database"},
            {"slug": "test-automation-engineer", "division": "quality", "description": "Test automation, TDD, test coverage"},
        ]
    return []


def make_fake_worker(return_value: Mapping[str, Any] | None = None, side_effect: Exception | None = None):
    """Create a fake READ-only worker that returns bounded structured output."""
    def worker(req: AgencyRequest, config: AgencyConfig) -> Mapping[str, Any]:
        if side_effect:
            raise side_effect
        if return_value is not None:
            return dict(return_value)
        # Default valid response
        return {
            "status": "succeeded",
            "summary": "Revisao documentada - simulacao local",
            "agent_slugs": list(req.specialists)[:2],
            "evidence_refs": ["fixture-local"],
            "proposed_changes": ["Sugestao — requer aprovacao humana"],
            "tests_run": [],
            "limitations": ["Teste simulado - LOCAL ONLY"],
        }
    return worker


def create_working_runtime(task_id: str, objective: str, area: str = "engineering",
                           max_inferences: int = 3) -> SelfWorkRuntime:
    """Create an active WORKING SelfWorkRuntime for testing."""
    rt = SelfWorkRuntime(id_factory=lambda: task_id, max_inferences=max_inferences)
    now = datetime.now(timezone.utc).isoformat()
    rt.propose(objective, area, now=now)
    rt.activate(now=now)
    rt.begin_work(now=now)
    assert rt.current is not None
    assert rt.current.state == SelfWorkState.WORKING
    assert rt.current.item_id == task_id
    return rt


def create_enabled_config(projects: tuple[str, ...] = ("atlas", "rei-da-laje", "lanchonete-do-guru")) -> AgencyConfig:
    """Create enabled AgencyConfig as in-memory unit-test object only."""
    return AgencyConfig(
        schema_version=1,
        enabled=True,
        worker_host="core",
        profile="atlas-specialists",
        max_agents=2,
        timeout_s=45.0,
        max_response_bytes=8192,
        projects=projects,
    )


class AgencyE2ECertificationTests(unittest.TestCase):
    """CP-AA6 LOCAL E2E certification tests - simulation only."""

    # --- Helper assertions ---

    def assert_event_clean(self, events: list[dict], objective: str):
        """Verify event contains no objective, secrets, or untrusted output."""
        for event in events:
            event_str = str(event)
            self.assertNotIn(objective, event_str, "Objective leaked into telemetry")
            # Check for secret patterns more precisely (not substrings in legitimate fields like task_id)
            import re
            secret_patterns = [
                r"bearer\s+\S+",
                r"(?:token|password|secret|api_key)\s*[:=]\s*\S+",
                r"sk(?:-proj)?-[a-zA-Z0-9_-]{8,}",
                r"ghp_[a-zA-Z0-9_-]{8,}",
                r"github_pat_[a-zA-Z0-9_-]{8,}",
            ]
            for pattern in secret_patterns:
                self.assertFalse(re.search(pattern, event_str, re.IGNORECASE),
                                 f"Secret pattern {pattern} leaked into telemetry")
            # Ensure only allowed keys
            allowed_keys = {"event_type", "task_id", "project", "status", "reason", "agent_count"}
            for key in event.keys():
                self.assertIn(key, allowed_keys, f"Unexpected telemetry key: {key}")

    def assert_policy_deny_by_default(self, project: str, objective: str, specialist: str):
        """Verify PolicyCapabilities.avaliar('task_specialist_review', ...).autorizada is False by default."""
        caps = PolicyCapabilities(atlas_capability_registry())
        decision = caps.avaliar("task_specialist_review", {
            "project": project,
            "objective": objective,
            "specialist": specialist,
        })
        self.assertFalse(decision.autorizada, f"PolicyCapabilities must deny by default for {project}/{specialist}")
        self.assertEqual(decision.autonomia, "DENY", f"Autonomy must be DENY, got {decision.autonomia}")
        self.assertEqual(decision.nivel, "READ", f"Capability level must be READ")

    def assert_bounded_structured_output(self, result: AgencyResult, expected_slugs: tuple[str, ...]):
        """Verify bounded structured output from AgencyGateway."""
        self.assertEqual(result.status, "succeeded")
        self.assertIsInstance(result.summary, str)
        self.assertLessEqual(len(result.summary), 4000)
        self.assertEqual(result.agent_slugs, expected_slugs)
        for slug in result.agent_slugs:
            self.assertTrue(slug.islower() or "-" in slug)
        self.assertLessEqual(len(result.evidence_refs), 16)
        self.assertLessEqual(len(result.proposed_changes), 12)
        self.assertLessEqual(len(result.tests_run), 16)
        self.assertLessEqual(len(result.limitations), 12)

    # --- Test Case 1: atlas monitoring services/architecture ---

    def test_atlas_monitoring_architecture_e2e(self):
        """CP-AA6: atlas project - monitoring services/architecture review (LOCAL SIMULATION)."""
        task_id = "atlas-mon-arch-01"
        objective = "Inspecionar monitoramento de servicos e arquitetura de observabilidade sem reiniciar nada"
        project = "atlas"
        expected_slugs = ("sre-site-reliability-engineer", "multi-agent-systems-architect")

        # Active WORKING SelfWorkRuntime
        rt = create_working_runtime(task_id, objective)

        # Config true only as in-memory unit-test object
        config = create_enabled_config(("atlas",))

        # Trusted candidate provider selects at most 2 specialists
        candidates = trusted_candidate_provider(project, objective)
        selected = select_specialists(project, objective, candidates, max_agents=2)
        self.assertEqual(selected, expected_slugs, "Correct slug selection via deterministic selector")

        # Verify READ AgencyRequest
        req = AgencyRequest(
            task_id=task_id,
            project=project,
            objective=objective,
            risk="READ",
            specialists=selected,
        )
        self.assertEqual(req.risk, "READ")
        self.assertEqual(req.specialists, expected_slugs)

        # Fake READ-only worker
        worker = make_fake_worker()
        events = []
        gateway = AgencyGateway(config, rt, worker, event_sink=events.append)

        # Execute
        result = gateway.execute(req)

        # Verify bounded structured output
        self.assert_bounded_structured_output(result, expected_slugs)

        # Event contains no objective or secrets
        self.assertEqual(len(events), 1)
        self.assert_event_clean(events, objective)
        self.assertEqual(events[0]["event_type"], "agency.specialist.result")
        self.assertEqual(events[0]["task_id"], task_id)
        self.assertEqual(events[0]["project"], project)
        self.assertEqual(events[0]["status"], "succeeded")
        self.assertEqual(events[0]["agent_count"], 2)

        # Verify canonical PolicyCapabilities(...).avaliar('task_specialist_review', params).autorizada remains false by default
        for slug in expected_slugs:
            self.assert_policy_deny_by_default(project, objective, slug)

        # Worker was called exactly once
        self.assertEqual(gateway.snapshot()["worker_attempts"], 1)
        self.assertEqual(gateway.snapshot()["succeeded"], 1)

    # --- Test Case 2: rei-da-laje pipa game/performance ---

    def test_rei_da_laje_pipa_game_performance_e2e(self):
        """CP-AA6: rei-da-laje project - pipa game/performance review (LOCAL SIMULATION)."""
        task_id = "rei-pipa-perf-01"
        objective = "Avaliar friccao continua no combate de pipa e benchmark de desempenho FPS sem alterar live"
        project = "rei-da-laje"
        expected_slugs = ("game-designer", "performance-benchmarker")

        rt = create_working_runtime(task_id, objective)
        config = create_enabled_config(("rei-da-laje",))

        candidates = trusted_candidate_provider(project, objective)
        selected = select_specialists(project, objective, candidates, max_agents=2)
        self.assertEqual(selected, expected_slugs)

        req = AgencyRequest(
            task_id=task_id,
            project=project,
            objective=objective,
            risk="READ",
            specialists=selected,
        )

        worker = make_fake_worker()
        events = []
        gateway = AgencyGateway(config, rt, worker, event_sink=events.append)
        result = gateway.execute(req)

        self.assert_bounded_structured_output(result, expected_slugs)

        self.assertEqual(len(events), 1)
        self.assert_event_clean(events, objective)
        self.assertEqual(events[0]["agent_count"], 2)

        for slug in expected_slugs:
            self.assert_policy_deny_by_default(project, objective, slug)

        self.assertEqual(gateway.snapshot()["worker_attempts"], 1)

    # --- Test Case 3: lanchonete-do-guru backend API/testes ---

    def test_lanchonete_do_guru_backend_api_testes_e2e(self):
        """CP-AA6: lanchonete-do-guru project - backend API/testes review (LOCAL SIMULATION)."""
        task_id = "lanchonete-bk-tst-01"
        objective = "Revisar arquitetura de API backend e cobertura de testes automatizados sem cobrar pagamentos"
        project = "lanchonete-do-guru"
        expected_slugs = ("backend-architect", "test-automation-engineer")

        rt = create_working_runtime(task_id, objective)
        config = create_enabled_config(("lanchonete-do-guru",))

        candidates = trusted_candidate_provider(project, objective)
        selected = select_specialists(project, objective, candidates, max_agents=2)
        self.assertEqual(selected, expected_slugs)

        req = AgencyRequest(
            task_id=task_id,
            project=project,
            objective=objective,
            risk="READ",
            specialists=selected,
        )

        worker = make_fake_worker()
        events = []
        gateway = AgencyGateway(config, rt, worker, event_sink=events.append)
        result = gateway.execute(req)

        self.assert_bounded_structured_output(result, expected_slugs)

        self.assertEqual(len(events), 1)
        self.assert_event_clean(events, objective)
        self.assertEqual(events[0]["agent_count"], 2)

        for slug in expected_slugs:
            self.assert_policy_deny_by_default(project, objective, slug)

        self.assertEqual(gateway.snapshot()["worker_attempts"], 1)

    # --- Adversarial Cases ---

    def test_invalid_no_candidates_no_worker_call(self):
        """Adversarial: invalid/no candidates -> no worker call."""
        task_id = "task-no-candidates"
        objective = "Inspecionar algo"
        project = "atlas"

        rt = create_working_runtime(task_id, objective)
        config = create_enabled_config(("atlas",))

        # Empty candidates -> select_specialists returns empty tuple
        candidates = []
        selected = select_specialists(project, objective, candidates, max_agents=2)
        self.assertEqual(selected, ())

        # AgencyRequest with empty specialists is valid but gateway should block
        req = AgencyRequest(task_id=task_id, project=project, objective=objective, risk="READ", specialists=())
        worker = Mock()
        gateway = AgencyGateway(config, rt, worker)

        # Gateway blocks due to no specialists matching (agent_budget_exceeded not triggered, but no specialists)
        # Actually the gateway allows empty specialists but worker won't be called if selection fails in TCE
        # Here we test the gateway directly with empty specialists - it will call worker
        # But the task requires "invalid/no candidates -> no worker call" at the TCE level
        # Let's test via TaskCapabilityExecutor which does the selection
        tce = TaskCapabilityExecutor(
            rt,
            specialist_gateway=gateway,
            specialist_candidate_provider=lambda p, o: [],  # No candidates
        )
        result = tce("task_specialist_review", {"project": project, "objective": objective, "specialist": "auto"})
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["error"], "agency_no_specialists")
        worker.assert_not_called()

    def test_paused_task_no_provider_no_worker(self):
        """Adversarial: paused task -> no provider/worker invocation."""
        task_id = "task-paused"
        objective = "Inspecionar pausado"
        project = "atlas"

        rt = create_working_runtime(task_id, objective)
        now = datetime.now(timezone.utc).isoformat()
        rt.pause_for_human(now=now)
        self.assertEqual(rt.current.state, SelfWorkState.PAUSED)

        config = create_enabled_config(("atlas",))
        worker = Mock()
        gateway = AgencyGateway(config, rt, worker)

        req = AgencyRequest(task_id=task_id, project=project, objective=objective, risk="READ", specialists=("sre",))
        result = gateway.execute(req)

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.reason, "task_not_active")
        worker.assert_not_called()

        # Also verify TCE blocks before provider call
        tce = TaskCapabilityExecutor(
            rt,
            specialist_gateway=gateway,
            specialist_candidate_provider=trusted_candidate_provider,
        )
        result2 = tce("task_specialist_review", {"project": project, "objective": objective, "specialist": "auto"})
        self.assertEqual(result2["status"], "ERROR")
        self.assertEqual(result2["error"], "agency_task_not_working")

    def test_off_config_no_invocation(self):
        """Adversarial: config disabled (off) -> no provider/worker invocation."""
        task_id = "task-off-config"
        objective = "Inspecionar com config off"
        project = "atlas"

        rt = create_working_runtime(task_id, objective)
        config = create_enabled_config(("atlas",))
        # Disable config
        config_disabled = AgencyConfig(
            schema_version=1,
            enabled=False,  # OFF
            worker_host="core",
            profile="atlas-specialists",
            max_agents=2,
            timeout_s=45.0,
            max_response_bytes=8192,
            projects=("atlas",),
        )

        worker = Mock()
        gateway = AgencyGateway(config_disabled, rt, worker)

        req = AgencyRequest(task_id=task_id, project=project, objective=objective, risk="READ", specialists=("sre",))
        result = gateway.execute(req)

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.reason, "feature_disabled")
        worker.assert_not_called()

        # TCE also checks config.enabled
        tce = TaskCapabilityExecutor(
            rt,
            specialist_gateway=gateway,
            specialist_candidate_provider=trusted_candidate_provider,
        )
        result2 = tce("task_specialist_review", {"project": project, "objective": objective, "specialist": "auto"})
        self.assertEqual(result2["status"], "ERROR")
        self.assertEqual(result2["error"], "agency_disabled")

    def test_malicious_worker_output_unexpected_actions_field_fails(self):
        """Adversarial: malicious worker output with unexpected executable 'actions' field -> failed/invalid_worker_result."""
        task_id = "task-malicious"
        objective = "Inspecionar com worker malicioso"
        project = "atlas"

        rt = create_working_runtime(task_id, objective)
        config = create_enabled_config(("atlas",))

        # Worker returns unexpected 'actions' field (executable commands)
        malicious_output = {
            "status": "succeeded",
            "summary": "ok",
            "agent_slugs": ["sre"],
            "actions": [{"type": "reboot", "host": "core"}]  # MALICIOUS: executable actions
        }
        worker = make_fake_worker(return_value=malicious_output)
        gateway = AgencyGateway(config, rt, worker)

        req = AgencyRequest(task_id=task_id, project=project, objective=objective, risk="READ", specialists=("sre",))
        result = gateway.execute(req)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.reason, "invalid_worker_result")
        self.assertIn("invalid_worker_result", gateway.snapshot()["failure_reasons"])

    def test_provider_raise_secrets_generic_error_no_leakage(self):
        """Adversarial: provider raises exception containing secrets -> generic error, no leakage."""
        task_id = "task-provider-secrets"
        objective = "Inspecionar com provider que vaza segredos"
        project = "atlas"

        rt = create_working_runtime(task_id, objective)
        config = create_enabled_config(("atlas",))

        def leaking_provider(project: str, objective: str) -> list[dict]:
            raise RuntimeError("Bearer secret-token-123 sk-proj-FAKEKEY github_pat_SECRET failed")

        tce = TaskCapabilityExecutor(
            rt,
            specialist_gateway=AgencyGateway(config, rt, make_fake_worker()),
            specialist_candidate_provider=leaking_provider,
        )
        result = tce("task_specialist_review", {"project": project, "objective": objective, "specialist": "auto"})

        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["error"], "agency_selection_invalid")
        # Verify no secrets leaked in result
        result_str = str(result)
        self.assertNotIn("secret", result_str.lower())
        self.assertNotIn("bearer", result_str.lower())
        self.assertNotIn("sk-proj", result_str.lower())
        self.assertNotIn("github_pat", result_str.lower())

    def test_stop_cancel_runtime_blocks_delegate(self):
        """Adversarial: stop/cancel runtime (ABANDONED/COMPLETED) blocks delegate."""
        task_id = "abandoned-01"
        objective = "Inspecionar apos abandon"
        project = "atlas"

        rt = create_working_runtime(task_id, objective)
        now = datetime.now(timezone.utc).isoformat()
        rt.abandon(now=now, reason="cancelled_by_operator")
        # After abandon, current is None (terminal state)
        self.assertIsNone(rt.current)

        config = create_enabled_config(("atlas",))
        worker = Mock()
        gateway = AgencyGateway(config, rt, worker)

        req = AgencyRequest(task_id=task_id, project=project, objective=objective, risk="READ", specialists=("sre",))
        result = gateway.execute(req)

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.reason, "task_not_active")
        worker.assert_not_called()

        # Also test COMPLETED state
        task_id2 = "completed-01"
        rt2 = create_working_runtime(task_id2, "Outra tarefa")
        rt2.review(now=now)
        rt2.complete(now=now)
        # After complete, current is None (terminal state)
        self.assertIsNone(rt2.current)

        gateway2 = AgencyGateway(config, rt2, worker)
        req2 = AgencyRequest(task_id=task_id2, project=project, objective=objective, risk="READ", specialists=("sre",))
        result2 = gateway2.execute(req2)
        self.assertEqual(result2.status, "blocked")
        self.assertEqual(result2.reason, "task_not_active")

    def test_deny_by_default_policy_remains_untouched(self):
        """Adversarial: deny-by-default PolicyCapabilities remains untouched across all projects."""
        # Test all three projects and their specialists (canonical slugs)
        test_cases = [
            ("atlas", "Inspecionar monitoramento", "sre-site-reliability-engineer"),
            ("atlas", "Inspecionar arquitetura", "multi-agent-systems-architect"),
            ("rei-da-laje", "Avaliar gameplay pipa", "game-designer"),
            ("rei-da-laje", "Benchmark FPS", "performance-benchmarker"),
            ("lanchonete-do-guru", "Revisar API backend", "backend-architect"),
            ("lanchonete-do-guru", "Cobertura testes", "test-automation-engineer"),
        ]

        for project, objective, specialist in test_cases:
            with self.subTest(project=project, specialist=specialist):
                self.assert_policy_deny_by_default(project, objective, specialist)

    # --- Integration with TaskCapabilityExecutor ---

    def test_tce_integration_full_flow_atlas(self):
        """Integration: TaskCapabilityExecutor with AgencyGateway for atlas project."""
        task_id = "task-tce-atlas"
        objective = "Inspecionar servicos e arquitetura"
        project = "atlas"

        rt = create_working_runtime(task_id, objective)
        config = create_enabled_config(("atlas",))
        worker = make_fake_worker()
        gateway = AgencyGateway(config, rt, worker)

        tce = TaskCapabilityExecutor(
            rt,
            specialist_gateway=gateway,
            specialist_candidate_provider=trusted_candidate_provider,
        )

        result = tce("task_specialist_review", {
            "project": project,
            "objective": objective,
            "specialist": "auto",
        })

        self.assertEqual(result["status"], "succeeded")
        self.assertIn("sre-site-reliability-engineer", result["agent_slugs"])
        self.assertIn("multi-agent-systems-architect", result["agent_slugs"])
        self.assertEqual(len(result["agent_slugs"]), 2)
        self.assertIsInstance(result["summary"], str)
        self.assertIsInstance(result["evidence_refs"], list)
        self.assertIsInstance(result["proposed_changes"], list)
        self.assertIsInstance(result["tests_run"], list)
        self.assertIsInstance(result["limitations"], list)

    def test_tce_integration_full_flow_rei_da_laje(self):
        """Integration: TaskCapabilityExecutor with AgencyGateway for rei-da-laje project."""
        task_id = "task-tce-rei"
        objective = "Avaliar fisica da pipa e performance"
        project = "rei-da-laje"

        rt = create_working_runtime(task_id, objective)
        config = create_enabled_config(("rei-da-laje",))
        worker = make_fake_worker()
        gateway = AgencyGateway(config, rt, worker)

        tce = TaskCapabilityExecutor(
            rt,
            specialist_gateway=gateway,
            specialist_candidate_provider=trusted_candidate_provider,
        )

        result = tce("task_specialist_review", {
            "project": project,
            "objective": objective,
            "specialist": "auto",
        })

        self.assertEqual(result["status"], "succeeded")
        self.assertIn("game-designer", result["agent_slugs"])
        self.assertIn("performance-benchmarker", result["agent_slugs"])
        self.assertEqual(len(result["agent_slugs"]), 2)

    def test_tce_integration_full_flow_lanchonete(self):
        """Integration: TaskCapabilityExecutor with AgencyGateway for lanchonete-do-guru project."""
        task_id = "task-tce-lanchonete"
        objective = "Revisar API e testes automatizados"
        project = "lanchonete-do-guru"

        rt = create_working_runtime(task_id, objective)
        config = create_enabled_config(("lanchonete-do-guru",))
        worker = make_fake_worker()
        gateway = AgencyGateway(config, rt, worker)

        tce = TaskCapabilityExecutor(
            rt,
            specialist_gateway=gateway,
            specialist_candidate_provider=trusted_candidate_provider,
        )

        result = tce("task_specialist_review", {
            "project": project,
            "objective": objective,
            "specialist": "auto",
        })

        self.assertEqual(result["status"], "succeeded")
        self.assertIn("backend-architect", result["agent_slugs"])
        self.assertIn("test-automation-engineer", result["agent_slugs"])
        self.assertEqual(len(result["agent_slugs"]), 2)

    # --- Explicit specialist (non-auto) still works ---

    def test_explicit_specialist_bypasses_selector_but_not_policy(self):
        """Explicit specialist=slug bypasses selector but PolicyCapabilities deny-by-default remains."""
        task_id = "task-explicit"
        objective = "Inspecionar com especialista explicito"
        project = "atlas"
        explicit_slug = "sre"

        rt = create_working_runtime(task_id, objective)
        config = create_enabled_config(("atlas",))
        worker = make_fake_worker()
        gateway = AgencyGateway(config, rt, worker)

        tce = TaskCapabilityExecutor(
            rt,
            specialist_gateway=gateway,
            specialist_candidate_provider=trusted_candidate_provider,
        )

        # Explicit specialist - selector not called
        result = tce("task_specialist_review", {
            "project": project,
            "objective": objective,
            "specialist": explicit_slug,
        })

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["agent_slugs"], [explicit_slug])

        # But PolicyCapabilities still denies by default
        caps = PolicyCapabilities(atlas_capability_registry())
        decision = caps.avaliar("task_specialist_review", {
            "project": project,
            "objective": objective,
            "specialist": explicit_slug,
        })
        self.assertFalse(decision.autorizada)
        self.assertEqual(decision.autonomia, "DENY")


if __name__ == "__main__":
    unittest.main()