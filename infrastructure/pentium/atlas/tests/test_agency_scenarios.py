"""READ-only scenario certification (simulation, NOT production E2E)."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from infrastructure.pentium.atlas.agency_specialists import AgencyConfig, AgencyRequest, AgencyGateway
from infrastructure.pentium.atlas.memory_store import MemoryStore
from infrastructure.pentium.atlas.self_work import SelfWorkRuntime


class AgencyScenarioTests(unittest.TestCase):
    def cfg(self):
        return AgencyConfig(1, True, "core", "atlas-specialists", 2, 45, 8192,
                            ("atlas", "rei-da-laje", "lanchonete-do-guru"))
    def test_read_only_three_projects_with_mocked_specialists(self):
        cases = [
            ("atlas", "Inspecionar saude sem reiniciar servicos", "sre"),
            ("rei-da-laje", "Inspecionar friccao continua sem alterar live", "game-designer"),
            ("lanchonete-do-guru", "Revisar arquitetura sem cobrar pagamentos", "software-architect"),
        ]
        for project, objective, slug in cases:
            with self.subTest(project=project):
                rt = SelfWorkRuntime(id_factory=lambda: "fixed-task", max_inferences=3)
                now = datetime.now(timezone.utc).isoformat()
                rt.propose(objective, "engineering", now=now)
                rt.activate(now=now); rt.begin_work(now=now)
                calls = []; events = []
                def reviewer(req, cfg):
                    calls.append(req)
                    return {"status": "succeeded", "summary": "Revisao documentada",
                            "agent_slugs": [slug], "evidence_refs": ["fixture"],
                            "proposed_changes": ["Sugestao — requer aprovacao humana"],
                            "tests_run": [], "limitations": ["Teste simulado"]}
                gateway = AgencyGateway(self.cfg(), rt, reviewer, event_sink=events.append)
                result = gateway.execute(AgencyRequest("fixed-task", project, objective, specialists=(slug,)))
                self.assertEqual("succeeded", result.status)
                self.assertEqual(1, len(calls))
                self.assertEqual("READ", calls[0].risk)
                self.assertEqual(1, len(events))
                self.assertNotIn(objective, str(events))
    def test_memory_reuses_existing_store_and_redacts_secrets(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(Path(td)/"existing-memory.db")
            try:
                rt = SelfWorkRuntime(id_factory=lambda: "memory-task", max_inferences=3)
                now = datetime.now(timezone.utc).isoformat()
                rt.propose("Read only", "engineering", now=now)
                rt.activate(now=now); rt.begin_work(now=now)
                def reviewer(req, cfg):
                    return {"status": "succeeded", "summary": "Revisado Bearer a-fake-secret",
                            "agent_slugs": ["sre"]}
                result = AgencyGateway(self.cfg(), rt, reviewer, memory_store=store).execute(
                    AgencyRequest("memory-task", "atlas", "Inspecionar"))
                self.assertEqual("succeeded", result.status)
                memo = store.get("agency:memory-task")
                self.assertIsNotNone(memo)
                self.assertNotIn("a-fake-secret", memo.content)
                self.assertIn("[REDACTED]", memo.content)
            finally:
                store.close()
    def test_pause_prevents_new_delegation_and_worker_not_invoked(self):
        rt = SelfWorkRuntime(id_factory=lambda: "paused-task")
        now = datetime.now(timezone.utc).isoformat()
        rt.propose("Inspect", "engineering", now=now)
        rt.activate(now=now); rt.begin_work(now=now)
        rt.pause_for_human(now=now)
        called = []
        gateway = AgencyGateway(self.cfg(), rt, lambda r,c: called.append(r))
        res = gateway.execute(AgencyRequest("paused-task", "atlas", "Inspecionar"))
        self.assertEqual("blocked", res.status)
        self.assertEqual([], called)
    def test_telemetry_and_memory_failures_do_not_corrupt_canonical_task(self):
        rt = SelfWorkRuntime(id_factory=lambda: "task", max_inferences=3)
        now = datetime.now(timezone.utc).isoformat()
        rt.propose("Inspect", "engineering", now=now)
        rt.activate(now=now); rt.begin_work(now=now)
        class FailedStore:
            def save(self, record):
                raise RuntimeError("storage unavailable")
        def broken(event):
            raise RuntimeError("event sink unavailable")
        payload = {"status": "succeeded", "summary": "ok", "agent_slugs": ["sre"]}
        res = AgencyGateway(self.cfg(), rt, lambda r,c: payload,
                            memory_store=FailedStore(), event_sink=broken).execute(
            AgencyRequest("task", "atlas", "Inspect", specialists=("sre",)))
        self.assertEqual("succeeded", res.status)
        self.assertEqual("WORKING", rt.current.state.value)


if __name__ == "__main__":
    unittest.main()
