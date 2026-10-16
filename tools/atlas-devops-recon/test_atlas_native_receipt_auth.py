import unittest
from datetime import datetime,timezone,timedelta
from atlas_native_receipt_auth import sign,verifier
NOW=datetime(2026,10,15,13,0,tzinfo=timezone.utc)
KEY=b"fixture-key-for-unit-tests-only-32bytes!"

class ReceiptAuthTests(unittest.TestCase):
    def receipt(self,**overrides):
        value=dict(task_id="task-a",session_id="session-a",outcome="succeeded",
                   cost=0,issued_at=NOW.isoformat(),issuer="sandbox-reviewer")
        value.update(overrides)
        value["signature"]=sign(value,KEY)
        return value
    def trusted(self):
        return verifier(KEY,expected_issuer="sandbox-reviewer",
                        expected_task="task-a",expected_session="session-a",now=NOW)
    def test_valid_receipt(self):
        self.assertTrue(self.trusted()(self.receipt()))
    def test_modified_payload_rejected(self):
        item=self.receipt()
        item["outcome"]="failed"
        self.assertFalse(self.trusted()(item))
    def test_wrong_session_rejected_even_if_signed(self):
        self.assertFalse(self.trusted()(self.receipt(session_id="other")))
    def test_expired_or_future_rejected(self):
        for moment in (NOW-timedelta(seconds=300),NOW+timedelta(seconds=1)):
            self.assertFalse(self.trusted()(self.receipt(issued_at=moment.isoformat())))
    def test_extra_fields_rejected(self):
        item=self.receipt()
        item["execution_authorized"]=True
        self.assertFalse(self.trusted()(item))
    def test_short_key_rejected(self):
        with self.assertRaises(ValueError):
            verifier(b"short",expected_issuer="x",expected_task="t",
                     expected_session="s",now=NOW)
