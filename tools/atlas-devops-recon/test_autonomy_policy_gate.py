"""CP11 autonomy policy, trusted inbox binding and rate-limit regression."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import tempfile,unittest,json
from durable_incidents import reconcile
from signed_event_transport import sign,receive
from autonomy_policy_gate import decide,reserve,validate_policy,SCHEMA
NOW=datetime(2026,10,14,17,0,tzinfo=timezone.utc)
KEY=bytes(range(32))
POLICY={"schema":SCHEMA,"enabled":True,"kill_switch":False,
        "mode":"observe_only","auto_approve":False,"auto_write":False,
        "allowed_actions":["diagnose_readonly"],"origins":["x99_worker"],
        "kinds":["worker_stale","worker_duplicate"],
        "limits":{"daily_readonly_missions":2,"max_concurrent":1,
                  "max_total_cost_usd":0}}
class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.inbox=self.root/"inbox.db";self.reserve_db=self.root/"reserve.db"
        self.out=self.root/"outbox"
        reconcile(self.root/"source.db",self.out,source="x99_worker",
                  findings={"worker_stale":{"summary":"observed"}},
                  at=NOW)
        self.proposal=json.loads(next(self.out.glob("*.json")).read_text())
        packet=sign(self.proposal,key=KEY,origin="x99_worker",now=NOW)
        receive(packet,key=KEY,db_path=self.inbox,now=NOW)
    def reserve(self,proposal=None,policy=None):
        return reserve(proposal or self.proposal,policy=policy or POLICY,
                       db_path=self.reserve_db,inbox_path=self.inbox,now=NOW)
    def test_authentic_readonly_reservation_has_no_execution(self):
        res=self.reserve()
        self.assertEqual(res["status"],"RESERVED_READONLY")
        self.assertFalse(res["execution_authorized"])
        self.assertTrue(res["requires_separate_dispatch"])
    def test_same_event_no_duplicate_reservation(self):
        self.reserve()
        self.assertEqual(self.reserve()["status"],"ALREADY_RESERVED")
    def test_forged_event_denied_without_receiver_ack(self):
        forged=dict(self.proposal,id="f"*32)
        self.assertEqual(self.reserve(forged)["status"],"UNVERIFIED_EVENT")
    def test_trusted_event_content_changed_denied(self):
        p=dict(self.proposal,summary="source altered")
        self.assertEqual(self.reserve(p)["status"],"UNVERIFIED_EVENT")
    def test_global_kill_switch(self):
        p=dict(POLICY,kill_switch=True)
        self.assertEqual(self.reserve(policy=p)["status"],"PAUSED")
        self.assertFalse(self.reserve(policy=p)["execution_authorized"])
    def test_no_self_approved_mutation(self):
        for key in ("auto_approve","auto_write"):
            with self.assertRaises(PermissionError):
                validate_policy(dict(POLICY,**{key:True}))
    def test_no_paid_or_unknown_action(self):
        p=dict(POLICY,limits=dict(POLICY["limits"],max_total_cost_usd=0.01))
        with self.assertRaises(PermissionError):validate_policy(p)
        p=dict(POLICY,allowed_actions=["deploy"])
        with self.assertRaises(PermissionError):validate_policy(p)
    def test_backpressure_prevents_second_open(self):
        self.reserve()
        reconcile(self.root/"source.db",self.out,source="x99_worker",
                  findings={"worker_stale":{"summary":"observed"},
                            "worker_duplicate":{"summary":"duplicate"}},
                  at=NOW+timedelta(seconds=1))
        second=next(json.loads(p.read_text()) for p in self.out.glob("*.json")
                    if json.loads(p.read_text())["kind"]=="worker_duplicate")
        receive(sign(second,key=KEY,origin="x99_worker",now=NOW),
                key=KEY,db_path=self.inbox,now=NOW)
        self.assertEqual(self.reserve(second)["status"],"BACKPRESSURE")
if __name__=="__main__":unittest.main()
