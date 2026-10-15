import unittest
from atlas.dispatch_composition import build_governed_dispatcher
from atlas.governed_dispatch import DispatchContext, ApprovalRequired

class CompositionTests(unittest.TestCase):
    def test_missing_provider_denied(self):
        with self.assertRaises(TypeError):
            build_governed_dispatcher(trusted_context_provider=None,
                                      infra_executor=lambda *a:None,workspace_executor=lambda *a:None)
    def test_real_dispatcher_denied_before_side_effect(self):
        calls=[]
        handler=lambda *args: calls.append(args) or {"ok":True}
        gateway=build_governed_dispatcher(trusted_context_provider=lambda:DispatchContext(
            "self","atlas",frozenset({"task_status"})),
            infra_executor=handler, workspace_executor=handler,git_executor=handler)
        with self.assertRaises(ApprovalRequired):
            gateway("git_push",{"scope":"atlas","receipt_verified":True})
        self.assertEqual(calls,[])
    def test_allowed_routes_to_underlying_executor(self):
        calls=[]
        handler=lambda *args: calls.append(args) or "ok"
        gateway=build_governed_dispatcher(trusted_context_provider=lambda:DispatchContext(
            "operator","atlas",frozenset({"workspace_list"})),
            infra_executor=handler, workspace_executor=handler)
        self.assertEqual(gateway("workspace_list",{}),"ok")
        self.assertEqual(len(calls),1)

if __name__=="__main__":unittest.main()
