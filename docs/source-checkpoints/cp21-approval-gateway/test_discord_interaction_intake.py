import json,unittest
from datetime import datetime,timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from atlas.discord_interaction_intake import parse_verified_interaction

class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.key=Ed25519PrivateKey.generate()
        self.public=self.key.public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex()
        self.now=datetime(2026,10,14,tzinfo=timezone.utc)
        self.ts=str(int(self.now.timestamp()))
    def request(self,payload,alter=False):
        raw=json.dumps(payload).encode()
        signature=self.key.sign(self.ts.encode()+raw).hex()
        if alter: raw+=b" "
        return parse_verified_interaction(public_key_hex=self.public,
             signature_hex=signature,timestamp=self.ts,raw_body=raw,now=self.now)
    def test_authenticated_member(self):
        event=self.request({"id":"123","channel_id":"456","member":{"user":{"id":"789"}}})
        self.assertEqual((event.actor_id,event.channel_id,event.interaction_id),("789","456","123"))
    def test_signature_failure(self):
        self.assertIsNone(self.request({"id":"123","channel_id":"456","member":{"user":{"id":"789"}}},True))
    def test_missing_identity_fails_closed(self):
        self.assertIsNone(self.request({"id":"123","channel_id":"456"}))
    def test_non_numeric_actor_denied(self):
        self.assertIsNone(self.request({"id":"123","channel_id":"456","member":{"user":{"id":"owner"}}}))
if __name__=="__main__":unittest.main()
