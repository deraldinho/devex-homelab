"""Non-destructive versioned schema gate for existing approval SQLite files."""
from contextlib import closing
import sqlite3

class MigrationBlocked(RuntimeError):
    pass

def migrate_approval_claims(db_path):
    with closing(sqlite3.connect(str(db_path),timeout=10,isolation_level=None)) as con:
        try:
            con.execute("BEGIN IMMEDIATE")
            tables={row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "approval_claims" not in tables:
                con.execute("""CREATE TABLE approval_claims(
                    nonce TEXT PRIMARY KEY, proposal_id TEXT NOT NULL UNIQUE,
                    proposal_hash TEXT NOT NULL, approver TEXT NOT NULL,
                    claimed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            else:
                cols={row[1] for row in con.execute("PRAGMA table_info(approval_claims)")}
                required={"nonce","proposal_id","proposal_hash","approver","claimed_at"}
                if not required <= cols:
                    raise MigrationBlocked("unexpected legacy schema")
                duplicates=con.execute("""SELECT proposal_id FROM approval_claims
                    GROUP BY proposal_id HAVING COUNT(*)>1 LIMIT 1""").fetchone()
                if duplicates:
                    raise MigrationBlocked("duplicate historical approvals require reconciliation")
                con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_approval_claims_proposal ON approval_claims(proposal_id)")
            con.execute("PRAGMA user_version=1")
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction: con.execute("ROLLBACK")
            raise
