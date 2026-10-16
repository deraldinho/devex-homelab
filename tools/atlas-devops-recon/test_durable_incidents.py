"""CP11 crash-safe incident ledger TDD; no production state touched."""
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from durable_incidents import reconcile,list_open,materialize

T=datetime(2026,10,14,16,0,tzinfo=timezone.utc)
WORK={"worker_not_running":{"summary":"worker stopped"}}
class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        p=Path(self.temp.name)
        self.db=p/"ledger.db";self.out=p/"outbox"
    def step(self,findings=WORK,at=T,fault=None,source="x99_worker"):
        return reconcile(self.db,self.out,findings=findings,source=source,at=at,fault=fault)
    def test_one_open_and_idempotent_repeated_probe(self):
        first=self.step();again=self.step(at=T+timedelta(minutes=5))
        self.assertEqual(len(first["opened"]),1)
        self.assertEqual(again["opened"],[])
        self.assertEqual(len(list(self.out.glob("*.json"))),1)
        self.assertEqual(len(list_open(self.db,"x99_worker")),1)
    def test_crash_before_commit_retries_same_occurrence(self):
        def boom(phase):
            if phase=="before_commit":raise OSError("power loss")
        with self.assertRaises(OSError):self.step(fault=boom)
        self.assertFalse(self.out.exists())
        self.assertEqual(len(self.step()["opened"]),1)
    def test_crash_after_commit_never_duplicates(self):
        def boom(phase):
            if phase=="after_commit":raise OSError("power loss")
        with self.assertRaises(OSError):self.step(fault=boom)
        again=self.step(at=T+timedelta(seconds=8))
        self.assertEqual(again["opened"],[])
        self.assertEqual(again["outbox_total"],1)
        self.assertEqual(len(list(self.out.glob("*.json"))),1)
    def test_crash_during_projection_repairs_file_idempotently(self):
        def boom(phase):
            if phase=="after_projection":raise OSError("disk failure")
        with self.assertRaises(OSError):self.step(fault=boom)
        second=self.step(at=T+timedelta(seconds=9))
        self.assertEqual(second["opened"],[])
        self.assertEqual(second["outbox_total"],1)
    def test_recovery_new_occurrence_after_resolution(self):
        first=self.step()
        recovery=self.step({},at=T+timedelta(minutes=1))
        self.assertEqual(recovery["resolved"],first["opened"])
        returned=self.step(at=T+timedelta(minutes=2))
        self.assertNotEqual(first["opened"],returned["opened"])
        self.assertEqual(len(list(self.out.glob("*.json"))),2)
        self.assertEqual(len(list_open(self.db,"x99_worker")),1)
    def test_no_execution_right_in_persisted_payload(self):
        result=self.step()
        item=json.loads(next(self.out.glob("*.json")).read_text())
        self.assertFalse(item["auto_execute"])
        self.assertTrue(item["requires_approval_for_changes"])
        self.assertEqual(result["execution_started"],False)
    def test_windows_pentium_namespaces_independent(self):
        self.step()
        inc=self.step({"atlas-cognitive":{"summary":"unit inactive"}},
                      source="pentium_services")
        self.assertEqual(len(inc["opened"]),1)
        self.assertEqual(len(list_open(self.db,"pentium_services")),1)
    def test_fail_closed_invalid_kind_source_and_tz(self):
        with self.assertRaises(ValueError):
            self.step({"run_shell":{"summary":"unsafe"}})
        with self.assertRaises(ValueError):
            self.step(source="attacker")
        with self.assertRaises(ValueError):
            self.step(at=datetime(2026,10,14))
    def test_missing_projection_rebuilt(self):
        self.step()
        next(self.out.glob("*.json")).unlink()
        self.assertEqual(materialize(self.db,self.out,source="x99_worker"),1)
        self.assertEqual(len(list(self.out.glob("*.json"))),1)

def _symlink_supported():
    try:
        root=tempfile.mkdtemp()
        try:
            target=Path(root)/"link"
            target.symlink_to(Path(root)/"backing")
            return True
        finally:
            Path(root, "link").unlink(missing_ok=True)
            import shutil
            shutil.rmtree(root, ignore_errors=True)
    except OSError:
        return False


@unittest.skipUnless(_symlink_supported(), "symlink creation requires privileges")
class SymlinkRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        p=Path(self.temp.name)
        self.db=p/"ledger.db";self.out=p/"outbox"
    def test_symlink_target_rejected_before_same_content(self):
        from durable_incidents import reconcile, materialize
        reconcile(self.db,self.out,source="x99_worker",
                  findings=WORK,at=T)
        target=next(self.out.glob("*.json"))
        content=target.read_text(encoding="utf-8")
        backing=self.out/"backing.json"
        backing.write_text(content,encoding="utf-8")
        target.unlink()
        target.symlink_to(backing)
        self.assertTrue(target.is_symlink())
        with self.assertRaises(PermissionError):
            materialize(self.db,self.out,source="x99_worker")
        self.assertTrue(target.is_symlink())
        self.assertEqual(backing.read_text(encoding="utf-8"),content)
    def test_symlink_target_not_overwritten_or_unlinked(self):
        from durable_incidents import reconcile, materialize
        reconcile(self.db,self.out,source="x99_worker",
                  findings=WORK,at=T)
        target=next(self.out.glob("*.json"))
        target.unlink()
        target.symlink_to(self.out/"missing.json")
        with self.assertRaises(PermissionError):
            materialize(self.db,self.out,source="x99_worker")
        self.assertTrue(target.is_symlink())


class SymlinkOrderRegressionTests(unittest.TestCase):
    def test_symlink_guard_precedes_same_content_return(self):
        from durable_incidents import reconcile, materialize
        from pathlib import Path
        import tempfile
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        p=Path(temp.name)
        db=p/"ledger.db"; out=p/"outbox"
        reconcile(db,out,source="x99_worker",findings=WORK,at=T)
        # Force is_symlink() True without requiring OS symlink privileges.
        original=Path.is_symlink
        Path.is_symlink=lambda self: True
        try:
            with self.assertRaises(PermissionError):
                materialize(db,out,source="x99_worker")
        finally:
            Path.is_symlink=original

if __name__=="__main__":unittest.main()
