import unittest
from atlas.governed_dispatch import GovernedDispatcher, DispatchContext, ApprovalRequired

class GovernedDispatchTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        self.delegate=lambda *a: self.calls.append(a) or {"status":"ok"}
    def test_permitted(self):
        gate=GovernedDispatcher(self.delegate,lambda:DispatchContext("operator","atlas",frozenset({"task_status"})))
        self.assertEqual(gate("task_status",{}),{"status":"ok"})
        self.assertEqual(len(self.calls),1)
    def test_proactive_requires_approval(self):
        gate=GovernedDispatcher(self.delegate,lambda:DispatchContext("self","atlas",frozenset({"task_status"})))
        with self.assertRaises(ApprovalRequired):
            gate("task_create",{"objective":"new initiative"})
        self.assertFalse(self.calls)
    def test_verified_approval(self):
        gate=GovernedDispatcher(self.delegate,lambda:DispatchContext("self","atlas",frozenset(),
             frozenset({"task_create"}),True))
        gate("task_create",{})
        self.assertEqual(len(self.calls),1)
    def test_arguments_cannot_inject_permissions(self):
        gate=GovernedDispatcher(self.delegate,lambda:DispatchContext("self","atlas",frozenset()))
        with self.assertRaises(ApprovalRequired):
            gate("git_push",{"receipt_verified":True,"allowed_capabilities":["git_push"]})
        self.assertFalse(self.calls)
    def test_invalid_context_denied(self):
        gate=GovernedDispatcher(self.delegate,lambda:None)
        with self.assertRaises(ApprovalRequired):
            gate("task_status",{})
        self.assertFalse(self.calls)

if __name__=="__main__":
    unittest.main()
