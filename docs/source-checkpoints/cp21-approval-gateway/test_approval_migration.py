import sqlite3,tempfile,unittest
from contextlib import closing
from pathlib import Path
from atlas.approval_migration import migrate_approval_claims,MigrationBlocked

class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/"old.db"
    def legacy(self):
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("""CREATE TABLE approval_claims(nonce TEXT PRIMARY KEY,
               proposal_id TEXT NOT NULL,proposal_hash TEXT NOT NULL,
               approver TEXT NOT NULL,claimed_at TEXT NOT NULL)""")
    def test_create_and_idempotence(self):
        migrate_approval_claims(self.db);migrate_approval_claims(self.db)
        with closing(sqlite3.connect(self.db)) as c, c:
            self.assertEqual(c.execute("PRAGMA user_version").fetchone()[0],1)
    def test_upgrade_preserves_rows(self):
        self.legacy()
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("INSERT INTO approval_claims VALUES('n','p','hash','owner','today')")
        migrate_approval_claims(self.db)
        with closing(sqlite3.connect(self.db)) as c, c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM approval_claims").fetchone()[0],1)
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("INSERT INTO approval_claims VALUES('n2','p','hash','owner','today')")
    def test_duplicates_fail_closed(self):
        self.legacy()
        with closing(sqlite3.connect(self.db)) as c, c:
            c.executemany("INSERT INTO approval_claims VALUES(?,?,?,?,?)",
                [('n1','p','hash','owner','today'),('n2','p','hash','owner','today')])
        with self.assertRaises(MigrationBlocked):migrate_approval_claims(self.db)
        with closing(sqlite3.connect(self.db)) as c, c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM approval_claims").fetchone()[0],2)
if __name__=="__main__":unittest.main()
