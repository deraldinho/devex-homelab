import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.cognitive_router import CognitiveRouter
from infrastructure.pentium.atlas.token_budget_governor import TokenBudgetGovernor
from infrastructure.pentium.atlas.workspace_health import WorkspaceEconomyPublisher
from infrastructure.pentium.atlas.workspace_policy import WorkspacePolicy
from infrastructure.pentium.atlas.workspace_broker import WorkspaceBroker
from infrastructure.pentium.atlas.self_work import SelfWorkRuntime


class WorkspaceRuntimeObservabilityTests(unittest.TestCase):
    def test_router_metrics_count_zero_token_routes(self):
        governor=TokenBudgetGovernor(window_budget=1000)
        router=CognitiveRouter(governor)
        router.route(kind='observation', fingerprint='a', operation='workspace_status')
        router.route(kind='observation', fingerprint='x')
        router.route(kind='observation', fingerprint='x')
        metrics=router.metrics()
        self.assertEqual(1, metrics['deterministic'])
        self.assertEqual(1, metrics['llm'])
        self.assertEqual(1, metrics['no_inference_required'])

    def test_publisher_writes_bounded_workspace_and_economy_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            broker=WorkspaceBroker(root/'ws', WorkspacePolicy())
            broker.write('notes','a.md','hello')
            governor=TokenBudgetGovernor(window_budget=1000); governor.record(120,category='human')
            router=CognitiveRouter(governor); router.route(kind='observation',fingerprint='a',operation='workspace_status')
            runtime=SelfWorkRuntime(id_factory=lambda:'sw-1')
            runtime.propose('organizar notas','notes',now='2026-09-12T19:00:00+00:00')
            out=root/'health.json'
            payload=WorkspaceEconomyPublisher(out).publish(broker=broker,governor=governor,router=router,self_work=runtime,expected_sha='a'*40)
            self.assertEqual('healthy',payload['status'])
            self.assertEqual(1,payload['workspace']['files'])
            self.assertEqual('CANDIDATE',payload['self_work']['state'])
            self.assertEqual('normal',payload['economy']['mode'])
            self.assertEqual('a'*40,payload['expected_sha'])
            self.assertTrue(out.is_file())
