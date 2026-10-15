import json,tempfile,unittest
from pathlib import Path
from dataclasses import replace
from datetime import datetime,timezone,timedelta
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from atlas.proposal_registry import ProposalRegistry
from atlas.discord_approval_boundary import ApprovalPlan
from atlas.discord_registered_approval import approve_registered_interaction

class RegisteredApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=ProposalRegistry(Path(self.tmp.name)/"p.db");self.store.initialize()
        self.now=datetime(2026,10,14,tzinfo=timezone.utc)
        self.plan=ApprovalPlan("p1",{"scope":"staging","steps":["test"]},"123","456",self.now+timedelta(minutes=10))
        self.store.register(self.plan)
        self.private=Ed25519PrivateKey.generate()
        self.pub=self.private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex()
    def approve(self,actor="123",digest=None,interaction="789"):
        ts=str(int(self.now.timestamp()))
        body=json.dumps({"id":interaction,"channel_id":"456","member":{"user":{"id":actor}}}).encode()
        return approve_registered_interaction(registry=self.store,proposal_id="p1",
            submitted_hash=digest if digest is not None else self.plan.digest(),
            public_key_hex=self.pub,signature_hex=self.private.sign(ts.encode()+body).hex(),
            timestamp=ts,raw_body=body,now=self.now)
    def test_registered_approval(self):
        self.assertTrue(self.approve())
        self.assertFalse(self.approve(interaction="790"))
    def test_wrong_hash_no_consumption(self):
        self.assertFalse(self.approve(digest="f"*64))
        self.assertTrue(self.approve())
    def test_wrong_actor(self):
        self.assertFalse(self.approve(actor="999"))
        self.assertTrue(self.approve())
if __name__=="__main__":unittest.main()
