"""TDD: bounded, default-off Agency specialists and existing SelfWork ownership."""
import json
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from infrastructure.pentium.atlas.agency_specialists import (
    AgencyConfig, AgencyRequest, AgencyGateway, HermesAgencyWorker,
    validate_plugin_manifest,
)
from infrastructure.pentium.atlas.self_work import SelfWorkRuntime


class AgencySpecialistsTests(unittest.TestCase):
    def setUp(self):
        self.runtime = SelfWorkRuntime(id_factory=lambda: "task-1", max_inferences=3)
        now = datetime.now(timezone.utc).isoformat()
        self.runtime.propose("revisar arquitetura", "engineering", now=now)
        self.runtime.activate(now=now)
        self.runtime.begin_work(now=now)
        self.req = AgencyRequest(task_id="task-1", project="rei-da-laje",
                                 objective="Diagnosticar colisao e IA", risk="READ",
                                 specialists=("game-designer", "performance-benchmarker"))
        self.worker = Mock(return_value={
            "status": "succeeded", "summary": "Diagnostico revisado",
            "agent_slugs": ["game-designer"], "evidence_refs": ["case-1"],
            "proposed_changes": ["Adicionar teste deterministico"],
            "tests_run": ["fixture-1"], "limitations": ["Sem benchmark fisico"]
        })

    def config(self, **overrides):
        cfg = dict(schema_version=1, enabled=True, worker_host="core",
                   profile="atlas-specialists", max_agents=2,
                   timeout_s=40, max_response_bytes=8192,
                   projects=("rei-da-laje", "atlas", "lanchonete-do-guru"))
        cfg.update(overrides)
        return AgencyConfig(**cfg)

    def test_disabled_is_fail_closed_and_does_not_call_worker(self):
        gateway = AgencyGateway(self.config(enabled=False), self.runtime, self.worker)
        result = gateway.execute(self.req)
        self.assertEqual("blocked", result.status)
        self.assertEqual("feature_disabled", result.reason)
        self.worker.assert_not_called()

    def test_only_read_risk_is_accepted(self):
        with self.assertRaises(ValueError):
            AgencyRequest(task_id="task-1", project="rei-da-laje", objective="deploy", risk="CONTROL")
        with self.assertRaises(ValueError):
            AgencyRequest(task_id="task-1", project="rei-da-laje", objective="deploy", risk="DESTRUCTIVE")

    def test_existing_task_identity_is_required(self):
        req = AgencyRequest(task_id="not-current", project="rei-da-laje", objective="inspecionar")
        result = AgencyGateway(self.config(), self.runtime, self.worker).execute(req)
        self.assertEqual("task_not_active", result.reason)
        self.worker.assert_not_called()

    def test_project_allowlist_blocks_worker(self):
        req = AgencyRequest(task_id="task-1", project="unknown", objective="inspecionar")
        result = AgencyGateway(self.config(), self.runtime, self.worker).execute(req)
        self.assertEqual("project_not_allowlisted", result.reason)
        self.worker.assert_not_called()

    def test_no_more_than_two_specialists(self):
        with self.assertRaises(ValueError):
            AgencyRequest(task_id="task-1", project="rei-da-laje", objective="inspecionar",
                          specialists=("game-designer", "qa-engineer", "sre"))
        self.worker.assert_not_called()

    def test_approved_review_returns_structured_evidence(self):
        gateway = AgencyGateway(self.config(), self.runtime, self.worker)
        result = gateway.execute(self.req)
        self.assertEqual("succeeded", result.status)
        self.assertEqual("Diagnostico revisado", result.summary)
        self.assertEqual(("case-1",), result.evidence_refs)
        self.assertEqual(1, gateway.snapshot()["succeeded"])
        self.assertEqual(1, self.runtime.current.inferences_used)

    def test_worker_error_is_bounded_and_does_not_leak_secret(self):
        self.worker.side_effect = RuntimeError("Bearer very-secret-value")
        gateway = AgencyGateway(self.config(), self.runtime, self.worker)
        result = gateway.execute(self.req)
        self.assertEqual("failed", result.status)
        self.assertEqual("worker_unavailable", result.reason)
        self.assertNotIn("secret", repr(result))

    def test_invalid_result_rejected_instead_of_executing_actions(self):
        self.worker.return_value = {"status": "succeeded", "summary": "ok",
                                    "agent_slugs": ["game-designer"], "actions": [{"type": "reboot"}]}
        result = AgencyGateway(self.config(), self.runtime, self.worker).execute(self.req)
        self.assertEqual("invalid_worker_result", result.reason)

    def test_unlisted_slug_not_accepted_from_worker(self):
        self.worker.return_value["agent_slugs"] = ["unknown"]
        result = AgencyGateway(self.config(), self.runtime, self.worker).execute(self.req)
        self.assertEqual("invalid_worker_result", result.reason)

    def test_config_default_is_disabled_and_validates_exact_fields(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "agency.json"
            p.write_text(json.dumps({"schema_version": 1, "enabled": False, "worker_host": "core",
                "profile": "atlas-specialists", "max_agents": 2, "timeout_s": 40,
                "max_response_bytes": 8192, "projects": ["atlas"]}))
            cfg = AgencyConfig.from_json(p)
            self.assertFalse(cfg.enabled)
            p.write_text(json.dumps({"schema_version": 1, "enabled": True, "worker_host": "pentium",
                "profile": "atlas", "max_agents": 99, "timeout_s": 0,
                "max_response_bytes": 8192, "projects": ["atlas"]}))
            with self.assertRaises(ValueError):
                AgencyConfig.from_json(p)

    def test_worker_uses_fixed_profile_argv_no_shell(self):
        import subprocess
        calls = []
        def fake_run(cmd, **kw):
            calls.append((cmd, kw))
            return subprocess.CompletedProcess(cmd, 0, json.dumps({
                "status": "succeeded", "summary": "ok", "agent_slugs": ["game-designer"],
                "evidence_refs": [], "tests_run": [], "limitations": [], "proposed_changes": []
            }), "")
        worker = HermesAgencyWorker("hermes", runner=fake_run)
        result = worker(self.req, self.config())
        self.assertEqual("succeeded", result["status"])
        cmd, kw = calls[0]
        self.assertEqual(["hermes", "-p", "atlas-specialists", "-z"], cmd[:4])
        self.assertNotIn("--yolo", cmd)
        self.assertFalse(kw["check"])
        self.assertEqual(40, kw["timeout"])

    def test_worker_refuses_oversized_response(self):
        import subprocess
        def fake_run(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 0, "a" * 10000, "")
        worker = HermesAgencyWorker("hermes", runner=fake_run)
        with self.assertRaises(ValueError):
            worker(self.req, self.config())

    def test_manifest_must_have_four_tools(self):
        self.assertFalse(validate_plugin_manifest("name: agency-agents-router\nprovides_tools:\n - agency_agents_search"))
        self.assertTrue(validate_plugin_manifest("name: agency-agents-router\nprovides_tools:\n - agency_agents_search\n - agency_agents_inspect\n - agency_agents_load\n - agency_agents_delegate"))

    def test_secret_redaction_handles_sk_proj_hyphenated_keys(self):
        """sk-proj- hyphenated OpenAI-style keys are redacted in episodic memory."""
        from infrastructure.pentium.atlas.agency_specialists import _SECRET
        # The regex should match sk-proj-... and sk-... hyphenated forms
        self.assertIsNotNone(_SECRET.search("Bearer abc123"))
        self.assertIsNotNone(_SECRET.search("token: secret-value"))
        self.assertIsNotNone(_SECRET.search("api_key=mykey"))
        self.assertIsNotNone(_SECRET.search("sk_abcdefgh1234"))
        self.assertIsNotNone(_SECRET.search("ghp_abcdefgh1234"))
        self.assertIsNotNone(_SECRET.search("github_pat_abcdefgh1234"))
        # New: hyphenated OpenAI keys
        self.assertIsNotNone(_SECRET.search("sk-proj-FAKESYNTHETIC123456"))
        self.assertIsNotNone(_SECRET.search("sk-FAKESYNTHETIC123456"))

    def test_memory_store_redacts_sk_proj_from_worker_summary(self):
        """Worker summary containing sk-proj- key gets redacted before MemoryStore.save."""
        memory_records = []
        class FakeMemoryStore:
            def save(self, record):
                memory_records.append(record)

        summary_with_secret = "Review done. Key sk-proj-FAKESYNTHETIC123456 used in config."
        worker = Mock(return_value={
            "status": "succeeded", "summary": summary_with_secret,
            "agent_slugs": ["game-designer"], "evidence_refs": ["case-1"],
            "proposed_changes": [], "tests_run": [], "limitations": []
        })
        gateway = AgencyGateway(self.config(), self.runtime, worker, memory_store=FakeMemoryStore())
        gateway.execute(self.req)

        self.assertEqual(1, len(memory_records))
        saved_content = memory_records[0].content
        # Secret should be redacted
        self.assertNotIn("sk-proj-FAKESYNTHETIC123456", saved_content)
        self.assertIn("[REDACTED]", saved_content)
        # Non-secret text should remain
        self.assertIn("Review done", saved_content)
        self.assertIn("used in config", saved_content)

    def test_memory_store_preserves_regular_text_no_false_positives(self):
        """Regular text without secrets passes through unchanged except length limit."""
        memory_records = []
        class FakeMemoryStore:
            def save(self, record):
                memory_records.append(record)

        normal_summary = "Diagnostico revisado sem credenciais aqui."
        worker = Mock(return_value={
            "status": "succeeded", "summary": normal_summary,
            "agent_slugs": ["game-designer"], "evidence_refs": ["case-1"],
            "proposed_changes": [], "tests_run": [], "limitations": []
        })
        gateway = AgencyGateway(self.config(), self.runtime, worker, memory_store=FakeMemoryStore())
        gateway.execute(self.req)

        self.assertEqual(1, len(memory_records))
        saved_content = memory_records[0].content
        self.assertEqual(normal_summary, saved_content)
        self.assertNotIn("[REDACTED]", saved_content)

    # --- Telemetry tests (RED phase) ---
    
    def test_snapshot_preserves_legacy_keys_and_adds_telemetry_fields(self):
        """Snapshot includes legacy keys plus new bounded telemetry fields."""
        gateway = AgencyGateway(self.config(), self.runtime, self.worker)
        snap = gateway.snapshot()
        # Legacy keys
        self.assertIn("enabled", snap)
        self.assertIn("succeeded", snap)
        self.assertIn("failed", snap)
        self.assertIn("blocked", snap)
        # New telemetry fields
        self.assertIn("worker_attempts", snap)
        self.assertIn("last_worker_duration_ms", snap)
        self.assertIn("worker_duration_total_ms", snap)
        self.assertIn("failure_reasons", snap)
        # Initial values
        self.assertEqual(snap["worker_attempts"], 0)
        self.assertEqual(snap["last_worker_duration_ms"], 0)
        self.assertEqual(snap["worker_duration_total_ms"], 0)
        self.assertEqual(snap["failure_reasons"], {})

    def test_worker_attempts_increments_on_failure_not_on_blocked(self):
        """Blocked requests do NOT increment worker_attempts; failures DO."""
        gateway = AgencyGateway(self.config(), self.runtime, self.worker)
        
        # Blocked: feature disabled
        gateway_disabled = AgencyGateway(self.config(enabled=False), self.runtime, self.worker)
        gateway_disabled.execute(self.req)
        self.assertEqual(gateway_disabled.snapshot()["worker_attempts"], 0)
        
        # Blocked: task not active
        gateway2 = AgencyGateway(self.config(), self.runtime, self.worker)
        req2 = AgencyRequest(task_id="not-current", project="rei-da-laje", objective="inspecionar")
        gateway2.execute(req2)
        self.assertEqual(gateway2.snapshot()["worker_attempts"], 0)
        
        # Blocked: project not allowlisted
        req3 = AgencyRequest(task_id="task-1", project="unknown", objective="inspecionar")
        gateway2.execute(req3)
        self.assertEqual(gateway2.snapshot()["worker_attempts"], 0)
        
        # Failure: worker returns invalid result -> increments attempts
        self.worker.return_value = {"status": "succeeded", "summary": "ok",
                                    "agent_slugs": ["game-designer"], "actions": [{"type": "reboot"}]}
        gateway3 = AgencyGateway(self.config(), self.runtime, self.worker)
        gateway3.execute(self.req)
        self.assertEqual(gateway3.snapshot()["worker_attempts"], 1)
        self.assertEqual(gateway3.snapshot()["failed"], 1)
        
        # Failure: worker exception -> increments attempts (same gateway)
        self.worker.side_effect = RuntimeError("worker down")
        gateway3.execute(self.req)
        self.assertEqual(gateway3.snapshot()["worker_attempts"], 2)
        self.assertEqual(gateway3.snapshot()["failed"], 2)

    def test_worker_duration_tracked_monotonic_ms(self):
        """Worker call duration recorded in monotonic milliseconds."""
        def slow_worker(req, cfg):
            time.sleep(0.01)  # 10ms
            return {"status": "succeeded", "summary": "ok", "agent_slugs": ["game-designer"],
                    "evidence_refs": [], "tests_run": [], "limitations": [], "proposed_changes": []}
        
        gateway = AgencyGateway(self.config(), self.runtime, slow_worker)
        gateway.execute(self.req)
        snap = gateway.snapshot()
        self.assertGreater(snap["last_worker_duration_ms"], 0)
        self.assertGreaterEqual(snap["last_worker_duration_ms"], 5)  # at least ~5ms
        self.assertEqual(snap["worker_duration_total_ms"], snap["last_worker_duration_ms"])
        self.assertEqual(snap["worker_attempts"], 1)
        
        # Second call adds to total
        gateway.execute(self.req)
        snap = gateway.snapshot()
        self.assertGreater(snap["worker_duration_total_ms"], snap["last_worker_duration_ms"])
        self.assertEqual(snap["worker_attempts"], 2)

    def test_failure_reasons_aggregates_code_defined_reasons(self):
        """failure_reasons counts code-defined reasons, not untrusted text."""
        gateway = AgencyGateway(self.config(), self.runtime, self.worker)
        
        # Trigger various failure reasons
        self.worker.return_value = {"status": "succeeded", "summary": "ok",
                                    "agent_slugs": ["game-designer"], "actions": [{"type": "reboot"}]}
        gateway.execute(self.req)  # invalid_worker_result
        
        self.worker.side_effect = RuntimeError("worker down")
        gateway.execute(self.req)  # worker_unavailable
        
        req_expired = AgencyRequest(task_id="task-1", project="rei-da-laje", objective="inspecionar")
        # Need to advance time to trigger expiration - but we can test other reasons
        gateway2 = AgencyGateway(self.config(), self.runtime, self.worker)
        req_bad_project = AgencyRequest(task_id="task-1", project="unknown", objective="inspecionar")
        gateway2.execute(req_bad_project)  # project_not_allowlisted (blocked, not attempt)
        
        snap = gateway.snapshot()
        reasons = snap["failure_reasons"]
        # Should have code-defined reason keys
        self.assertIn("invalid_worker_result", reasons)
        self.assertIn("worker_unavailable", reasons)
        self.assertEqual(reasons["invalid_worker_result"], 1)
        self.assertEqual(reasons["worker_unavailable"], 1)
        # Blocked reasons should NOT be in failure_reasons (only failed attempts)
        self.assertNotIn("project_not_allowlisted", reasons)
        self.assertNotIn("feature_disabled", reasons)
        self.assertNotIn("task_not_active", reasons)

    def test_telemetry_optional_in_memory_no_crash_selfwork(self):
        """Telemetry is optional, in-memory, and never crashes SelfWork."""
        # Gateway without event_sink and memory_store still works
        gateway = AgencyGateway(self.config(), self.runtime, self.worker)
        result = gateway.execute(self.req)
        self.assertEqual("succeeded", result.status)
        snap = gateway.snapshot()
        self.assertEqual(snap["worker_attempts"], 1)
        self.assertGreaterEqual(snap["last_worker_duration_ms"], 0)
        
        # Even if event_sink raises, execute succeeds (fresh runtime to avoid inference budget)
        def bad_sink(event):
            raise RuntimeError("sink failed")
        runtime2 = SelfWorkRuntime(id_factory=lambda: "task-2", max_inferences=3)
        now = datetime.now(timezone.utc).isoformat()
        runtime2.propose("revisar arquitetura", "engineering", now=now)
        runtime2.activate(now=now)
        runtime2.begin_work(now=now)
        req2 = AgencyRequest(task_id="task-2", project="rei-da-laje",
                             objective="Diagnosticar colisao e IA", risk="READ",
                             specialists=("game-designer", "performance-benchmarker"))
        gateway2 = AgencyGateway(self.config(), runtime2, self.worker, event_sink=bad_sink)
        result2 = gateway2.execute(req2)
        self.assertEqual("succeeded", result2.status)
        
        # Even if memory_store raises, execute succeeds (fresh runtime)
        class BadMemory:
            def save(self, record):
                raise RuntimeError("memory failed")
        runtime3 = SelfWorkRuntime(id_factory=lambda: "task-3", max_inferences=3)
        runtime3.propose("revisar arquitetura", "engineering", now=now)
        runtime3.activate(now=now)
        runtime3.begin_work(now=now)
        req3 = AgencyRequest(task_id="task-3", project="rei-da-laje",
                             objective="Diagnosticar colisao e IA", risk="READ",
                             specialists=("game-designer", "performance-benchmarker"))
        gateway3 = AgencyGateway(self.config(), runtime3, self.worker, memory_store=BadMemory())
        result3 = gateway3.execute(req3)
        self.assertEqual("succeeded", result3.status)

    def test_no_secrets_objectives_prompts_in_telemetry(self):
        """Telemetry never includes objectives, secrets, prompts, or untrusted text."""
        # Worker that might leak secrets in error
        leaky_worker = Mock(side_effect=RuntimeError("Bearer secret-token-123 failed"))
        gateway = AgencyGateway(self.config(), self.runtime, leaky_worker)
        gateway.execute(self.req)
        snap = gateway.snapshot()
        # failure_reasons should only have code-defined keys, not the error message
        self.assertIn("worker_unavailable", snap["failure_reasons"])
        # Ensure no secret leaked into any telemetry field
        for key, val in snap.items():
            if isinstance(val, dict):
                for k, v in val.items():
                    self.assertNotIn("secret", str(k).lower())
                    self.assertNotIn("secret", str(v).lower())
                    self.assertNotIn("bearer", str(k).lower())
                    self.assertNotIn("bearer", str(v).lower())
            self.assertNotIn("secret", str(val).lower())
            self.assertNotIn("bearer", str(val).lower())
        # Objective not in snapshot
        self.assertNotIn("Diagnosticar", str(snap))

    def test_failure_reasons_cardinality_bounded(self):
        """failure_reasons dict has bounded cardinality (only known code reasons)."""
        known_reasons = {
            "invalid_worker_result", "worker_unavailable", "output_budget_exceeded",
            "input_budget_exceeded", "worker_error", "result_schema_invalid",
            "result_status_invalid", "result_slugs_invalid", "unexpected_agent",
            "invalid_task_id", "invalid_project", "invalid_repo_commit",
        }
        gateway = AgencyGateway(self.config(), self.runtime, self.worker)
        
        # Generate several different failures
        self.worker.return_value = {"status": "succeeded", "summary": "ok",
                                    "agent_slugs": ["game-designer"], "actions": [{"type": "reboot"}]}
        gateway.execute(self.req)
        
        self.worker.side_effect = RuntimeError("down")
        gateway.execute(self.req)
        
        self.worker.side_effect = ValueError("output_budget_exceeded")
        gateway.execute(self.req)
        
        snap = gateway.snapshot()
        reasons = snap["failure_reasons"]
        # All keys must be from known set
        for reason in reasons:
            self.assertIn(reason, known_reasons, f"Unknown failure reason: {reason}")
        # Cardinality bounded by known reasons
        self.assertLessEqual(len(reasons), len(known_reasons))

if __name__ == "__main__":
    unittest.main()
