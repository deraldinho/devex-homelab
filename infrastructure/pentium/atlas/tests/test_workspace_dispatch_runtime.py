import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.workspace_broker import WorkspaceBroker
from infrastructure.pentium.atlas.workspace_policy import WorkspacePolicy
from infrastructure.pentium.atlas.workspace_index import WorkspaceIndex
from infrastructure.pentium.atlas.workspace_retriever import WorkspaceRetriever
from infrastructure.pentium.atlas.workspace_capability_executor import WorkspaceCapabilityExecutor
from infrastructure.pentium.atlas.self_work import SelfWorkRuntime
from infrastructure.pentium.atlas.capability_dispatch import CapabilityDispatcher


class WorkspaceDispatchRuntimeTests(unittest.TestCase):
    def test_write_reindexes_and_debits_self_work_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            broker=WorkspaceBroker(root/'ws',WorkspacePolicy())
            index=WorkspaceIndex(root/'index.db')
            runtime=SelfWorkRuntime(max_operations=4,id_factory=lambda:'sw')
            runtime.propose('nota','notes',now='2026-09-12T19:00:00+00:00'); runtime.activate(now='2026-09-12T19:00:01+00:00')
            executor=WorkspaceCapabilityExecutor(broker,searcher=WorkspaceRetriever(index),indexer=index,self_work=runtime)
            executor('workspace_write',{'area':'notes','path':'core.md','content':'runner core estável'},None,None)
            self.assertEqual(1,runtime.current.operations_used)
            self.assertEqual('notes/core.md',index.search('runner core')[0]['path'])
            index.close()

    def test_dispatcher_never_sends_workspace_to_infra_executor(self):
        seen=[]
        dispatcher=CapabilityDispatcher(lambda *args: seen.append(('infra',args)), lambda *args: seen.append(('workspace',args)))
        dispatcher('workspace_status',{},None,None)
        dispatcher('restart_service',{'host':'pentium','service':'atlas-dashboard.service'},None,None)
        self.assertEqual(['workspace','infra'],[item[0] for item in seen])
