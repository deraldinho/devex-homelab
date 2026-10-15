import unittest
from datetime import datetime,timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from atlas.discord_signature import verify_discord_request

class DiscordSignatureTests(unittest.TestCase):
    def setUp(self):
        self.private=Ed25519PrivateKey.generate()
        self.key=self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw).hex()
        self.now=datetime(2026,10,14,tzinfo=timezone.utc)
        self.ts=str(int(self.now.timestamp()))
        self.body=b'{"type":1}'
        self.sig=self.private.sign(self.ts.encode()+self.body).hex()
    def check(self,**overrides):
        args=dict(public_key_hex=self.key,signature_hex=self.sig,
                  timestamp=self.ts,raw_body=self.body,now=self.now)
        args.update(overrides)
        return verify_discord_request(**args)
    def test_authentic(self): self.assertTrue(self.check())
    def test_tampered_body(self): self.assertFalse(self.check(raw_body=b'{"type":2}'))
    def test_modified_signature(self): self.assertFalse(self.check(signature_hex="0"*128))
    def test_expired(self): self.assertFalse(self.check(timestamp=str(int(self.ts)-500)))
    def test_future_timestamp(self): self.assertFalse(self.check(timestamp=str(int(self.ts)+500)))
    def test_invalid_key(self): self.assertFalse(self.check(public_key_hex="not_a_key"))
    def test_bad_window(self): self.assertFalse(self.check(max_age_seconds=900))

if __name__=="__main__":unittest.main()
