"""TDD CP11 signed event delivery and receiver idempotence."""
import tempfile,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from durable_incidents import reconcile
from signed_event_transport import sign,receive

KEY=bytes(range(32))
NOW=datetime(2026,10,14,15,0,tzinfo=timezone.utc)
class TransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.out=self.root/"outbox"
        self.db=self.root/"ledger.db"
        self.inbox=self.root/"inbox.db"
        reconcile(self.db,self.out,source="x99_worker",
            findings={"worker_stale":{"summary":"heartbeat lagging"}},at=NOW)
        import json
        self.event=__import__("json").loads(next(self.out.glob("*.json")).read_text())
    def signed(self,proposal=None,**kwargs):
        return sign(proposal or self.event,key=KEY,origin="x99_worker",now=NOW,**kwargs)
    def recv(self,env,now=NOW):
        return receive(env,key=KEY,db_path=self.inbox,now=now)
    def test_verified_acceptance_and_at_most_once_ack(self):
        env=self.signed()
        first=self.recv(env)
        second=self.recv(env)
        self.assertEqual(first["status"],"accepted")
        self.assertEqual(second["status"],"duplicate")
        self.assertEqual(first["ack"],second["ack"])
        self.assertEqual(first["execution_started"],False)
    def test_forged_signature_and_missing_key_rejected(self):
        env=self.signed()
        env["signature"]="f"*64
        with self.assertRaises(PermissionError):self.recv(env)
        with self.assertRaises(ValueError):
            receive(env,key=b"",db_path=self.inbox,now=NOW)
    def test_unsigned_scope_escalation_rejected_even_if_resigned(self):
        event=dict(self.event,auto_execute=True)
        with self.assertRaises(PermissionError):
            self.signed(event)
        env=self.signed()
        env["proposal"]["auto_execute"]=True
        with self.assertRaises(PermissionError):self.recv(env)
    def test_timestamp_expiry(self):
        env=self.signed()
        with self.assertRaises(PermissionError):
            self.recv(env,now=NOW+timedelta(hours=2))
    def test_resolution_requires_open_and_unique(self):
        resolved=dict(self.event,status="RESOLVED",resolved_at=NOW.isoformat())
        packet=self.signed(resolved)
        with self.assertRaises(ValueError):
            self.recv(packet)
        self.recv(self.signed())
        self.assertEqual(self.recv(packet)["status"],"accepted")
        self.assertEqual(self.recv(packet)["status"],"duplicate")
    def test_different_content_same_event_id_blocked(self):
        first=self.signed()
        self.recv(first)
        second=dict(self.event,summary="tampered legitimate same id")
        with self.assertRaises(PermissionError):
            self.recv(self.signed(second))
    def test_wrong_origin_rejected(self):
        event=dict(self.event,origin="pentium_services")
        with self.assertRaises(ValueError):
            self.signed(event)
if __name__=="__main__": unittest.main()
