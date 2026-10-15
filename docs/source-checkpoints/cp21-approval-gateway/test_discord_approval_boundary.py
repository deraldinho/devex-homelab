import tempfile, unittest
from pathlib import Path
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from atlas.approval_inbox import DurableApprovalInbox
from atlas.discord_approval_boundary import ApprovalPlan, TrustedDiscordEvent, accept_approval

class DiscordApprovalBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.inbox=DurableApprovalInbox(Path(self.tmp.name)/"gate.db")
        self.inbox.initialize()
        self.now=datetime(2026,10,14,tzinfo=timezone.utc)
        self.plan=ApprovalPlan("p1",{"steps":["audit","test"],"scope":"atlas"},"owner","private",
                               self.now+timedelta(minutes=10))
        self.event=TrustedDiscordEvent("owner","private","interaction-1",True)
    def accept(self,plan=None,event=None,digest=None):
        plan=plan or self.plan
        return accept_approval(self.inbox,plan=plan,event=event or self.event,
                 submitted_hash=digest if digest is not None else self.plan.digest(),now=self.now)
    def test_valid_once(self):
        self.assertTrue(self.accept())
        self.assertFalse(self.accept())
    def test_unverified_denied(self):
        self.assertFalse(self.accept(event=replace(self.event,signature_verified=False)))
    def test_wrong_actor_denied(self):
        self.assertFalse(self.accept(event=replace(self.event,actor_id="attacker")))
    def test_wrong_channel_denied(self):
        self.assertFalse(self.accept(event=replace(self.event,channel_id="public")))
    def test_changed_plan_denied(self):
        self.assertFalse(self.accept(plan=replace(self.plan,content={"steps":["deploy"]})))
    def test_expired_denied(self):
        self.assertFalse(self.accept(plan=replace(self.plan,expires_at=self.now-timedelta(seconds=1))))
    def test_wrong_digest_denied(self):
        self.assertFalse(self.accept(digest="0"*64))
if __name__=="__main__":unittest.main()
