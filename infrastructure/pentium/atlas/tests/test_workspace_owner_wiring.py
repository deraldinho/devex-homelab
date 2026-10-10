import unittest
from pathlib import Path


class WorkspaceOwnerWiringTests(unittest.TestCase):
    def test_owner_wires_workspace_economy_without_expanding_infra_scope(self):
        root=Path(__file__).resolve().parents[1]
        source=(root/'cognitive_daemon.py').read_text(encoding='utf-8')
        for token in (
            'WorkspaceBroker(', 'WorkspaceIndex(', 'WorkspaceContextCache(',
            'WorkspaceRetriever(', 'TokenBudgetGovernor(', 'CognitiveRouter(',
            'SelfWorkRuntime(', 'WorkspaceCapabilityExecutor(', 'CapabilityDispatcher(',
            'WorkspaceEconomyPublisher(',
        ):
            self.assertIn(token,source)
        self.assertIn('AGENT_ROOT/"atlas-workspace"',source)
        compact=source.replace(' ','')
        self.assertIn('auto_service_targets=(("pentium","atlas-observation.service"),("pentium","atlas-dashboard.service"))',compact)
        self.assertNotIn('auto_hosts=("pentium","core"',compact)
        self.assertNotIn('auto_hosts=("pentium","x99","core")',compact)

    def test_installer_packages_workspace_runtime_modules(self):
        root=Path(__file__).resolve().parents[1]
        install=(root/'install-user.sh').read_text(encoding='utf-8')
        for token in ('workspace_policy.py','workspace_broker.py','workspace_index.py','workspace_retriever.py','workspace_context_cache.py','token_budget_governor.py','cognitive_router.py','context_pack.py','self_work.py','workspace_capability_executor.py','capability_dispatch.py','workspace_health.py'):
            self.assertGreaterEqual(install.count(token),2,token)

if __name__=='__main__': unittest.main()
