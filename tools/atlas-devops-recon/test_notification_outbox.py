"""CP11 notification dedup, pause, one-send, ambiguous result."""
import tempfile,unittest
from pathlib import Path
from notification_outbox import prepare,dispatch_one
from signed_event_transport import sign,receive
class Notifications(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/"notifications.db"
        self.inbox=Path(self.tmp.name)/"verified-inbox.db"
        self.p={"schema":"atlas.collective.proposal.v2",
                "id":"b"*32,"origin":"x99_worker","kind":"worker_stale",
                "status":"PROPOSED","auto_execute":False,
                "requires_approval_for_changes":True,
                "allowed_actions":["observe","diagnose","report"],
                "summary":"Heartbeat overdue"}
        from datetime import datetime,timezone
        now=datetime.now(timezone.utc)
        envelope=sign(self.p,key=bytes(range(32)),origin="x99_worker",now=now)
        receive(envelope,key=bytes(range(32)),db_path=self.inbox,now=now)
    def test_dedup_queue(self):
        self.assertEqual(prepare(self.p,db_path=self.db,verified_inbox=self.inbox)["status"],"queued")
        self.assertEqual(prepare(self.p,db_path=self.db,verified_inbox=self.inbox)["status"],"already_queued")
    def test_no_dispatch_without_explicit_config(self):
        ident=prepare(self.p,db_path=self.db,verified_inbox=self.inbox)["id"]
        with self.assertRaises(PermissionError):
            dispatch_one(db_path=self.db,id=ident,sender=lambda x:self.fail("unexpected send"))
    def test_exact_single_delivery(self):
        ident=prepare(self.p,db_path=self.db,verified_inbox=self.inbox)["id"]
        sent=[]
        def sender(p):
            sent.append(p)
            return {"receipt":"provider-msg-1"}
        self.assertEqual(dispatch_one(db_path=self.db,id=ident,sender=sender,
                                      explicit_enabled=True)["status"],"delivered")
        self.assertEqual(dispatch_one(db_path=self.db,id=ident,sender=sender,
                                      explicit_enabled=True)["status"],"blocked_no_pending")
        self.assertEqual(len(sent),1)
    def test_ambiguous_transport_never_retries_blindly(self):
        ident=prepare(self.p,db_path=self.db,verified_inbox=self.inbox)["id"]
        seen=[]
        def sender(p):
            seen.append(p)
            raise TimeoutError("provider timeout after potential delivery")
        self.assertEqual(dispatch_one(db_path=self.db,id=ident,sender=sender,
                                      explicit_enabled=True)["status"],"NEEDS_RECONCILIATION")
        self.assertEqual(dispatch_one(db_path=self.db,id=ident,sender=sender,
                                      explicit_enabled=True)["status"],"blocked_no_pending")
        self.assertEqual(len(seen),1)
    def test_other_origin_rejected(self):
        self.p["origin"]="attacker"
        with self.assertRaises(PermissionError):prepare(self.p,db_path=self.db,verified_inbox=self.inbox)
if __name__=="__main__":unittest.main()
