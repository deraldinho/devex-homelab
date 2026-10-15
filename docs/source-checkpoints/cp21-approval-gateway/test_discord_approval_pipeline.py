import json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from atlas.proposal_registry import ProposalRegistry
from atlas.discord_approval_boundary import ApprovalPlan
from atlas.discord_approval_pipeline import approve_signed_discord_interaction

class ApprovalPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.registry=ProposalRegistry(Path(self.tmp.name)/"p.db")
        self.registry.initialize()
        self.now=datetime(2026,10,14,tzinfo=timezone.utc)
        self.plan=ApprovalPlan("proposal-1",{"steps":["test"],"scope":"atlas"},
             "1001","2002",self.now+timedelta(minutes=5))
        self.private=Ed25519PrivateKey.generate()
        self.public=self.private.public_key().public_bytes(
             serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex()
    def send(self,*,actor="1001",interaction="3003",tamper=False):
        timestamp=str(int(self.now.timestamp()))
        body=json.dumps({"id":interaction,"channel_id":"2002","member":{"user":{"id":actor}}}).encode()
        signature=self.private.sign(timestamp.encode()+body).hex()
        if tamper: body+=b" "
        return approve_signed_discord_interaction(registry=self.registry,plan=self.plan,
              public_key_hex=self.public,signature_hex=signature,timestamp=timestamp,
              raw_body=body,submitted_hash=self.plan.digest(),now=self.now)
    def test_unregistered_denied(self):self.assertFalse(self.send())
    def test_verified_once(self):
        self.registry.register(self.plan)
        self.assertTrue(self.send())
        self.assertFalse(self.send(interaction="3999"))
    def test_tamper_denied(self):
        self.registry.register(self.plan)
        self.assertFalse(self.send(tamper=True))
        self.assertTrue(self.send())
    def test_wrong_actor_denied(self):
        self.registry.register(self.plan)
        self.assertFalse(self.send(actor="9999"))
if __name__=="__main__": unittest.main()
