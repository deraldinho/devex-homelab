"""Durable single-use approval claims; cryptographic verification is external.
Call claim only after authenticated Discord gateway verified message and plan hash.
"""
from __future__ import annotations
import sqlite3
from contextlib import closing
from pathlib import Path

class DurableApprovalInbox:
    def __init__(self, db: str | Path):
        self.db = str(db)

    def initialize(self):
        with closing(sqlite3.connect(self.db, timeout=10)) as con, con:
            con.execute("""CREATE TABLE IF NOT EXISTS approval_claims (
                nonce TEXT PRIMARY KEY, proposal_id TEXT NOT NULL UNIQUE,
                proposal_hash TEXT NOT NULL, approver TEXT NOT NULL,
                claimed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")

    def claim(self, *, nonce: str, proposal_id: str, proposal_hash: str,
              approver: str, verified: bool, unexpired: bool) -> bool:
        if not (verified and unexpired and nonce and proposal_id and proposal_hash and approver):
            return False
        if len(nonce) > 256 or len(proposal_id) > 256 or len(proposal_hash) != 64:
            return False
        try:
            int(proposal_hash, 16)
        except ValueError:
            return False
        # SQLite unique constraint ensures only one claimant wins across processes.
        with closing(sqlite3.connect(self.db, timeout=10)) as con, con:
            try:
                con.execute("INSERT INTO approval_claims(nonce,proposal_id,proposal_hash,approver) VALUES (?,?,?,?)",
                            (nonce,proposal_id,proposal_hash,approver))
                return True
            except sqlite3.IntegrityError:
                return False
