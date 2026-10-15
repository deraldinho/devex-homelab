import tempfile,unittest
from pathlib import Path
from dataclasses import replace
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor
from atlas.proposal_registry import ProposalRegistry
from atlas.discord_approval_boundary import ApprovalPlan,TrustedDiscordEvent

class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=ProposalRegistry(Path(self.tmp.name)/"approvals.db");self.store.initialize()
        self.now=datetime(2026,10,14,tzinfo=timezone.utc)
        self.plan=ApprovalPlan("p1",{"task":"audit"},"123","456",self.now+timedelta(minutes=10))
        self.ev=TrustedDiscordEvent("123","456","789",True)
    def accept(self,**kwargs):
        return self.store.approve(self.plan,self.ev,submitted_hash=self.plan.digest(),now=self.now,**kwargs)
    def test_unregistered_denied(self):self.assertFalse(self.accept())
    def test_registered_approves_once(self):
        self.assertTrue(self.store.register(self.plan))
        self.assertTrue(self.accept())
        self.assertFalse(self.accept())
    def test_plan_mutation_rejected(self):
        self.store.register(self.plan)
        self.assertFalse(self.store.approve(replace(self.plan,content={"task":"deploy"}),self.ev,submitted_hash=self.plan.digest(),now=self.now))
    def test_unverified_denied(self):
        self.store.register(self.plan)
        self.assertFalse(self.store.approve(self.plan,replace(self.ev,signature_verified=False),submitted_hash=self.plan.digest(),now=self.now))
    def test_concurrent_approval_single_winner(self):
        self.store.register(self.plan)
        with ThreadPoolExecutor(max_workers=4) as pool:
            outcome=list(pool.map(lambda i:self.store.approve(self.plan,replace(self.ev,interaction_id=str(i)),submitted_hash=self.plan.digest(),now=self.now),range(6)))
        self.assertEqual(outcome.count(True),1)
    def test_conflicting_registration_rejected(self):
        self.store.register(self.plan)
        with self.assertRaises(ValueError):
            self.store.register(replace(self.plan,content={"task":"other"}))
if __name__=="__main__":unittest.main()
