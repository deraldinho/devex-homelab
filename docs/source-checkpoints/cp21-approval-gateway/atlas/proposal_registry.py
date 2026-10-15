"""Transactional registry for proposed initiatives and approvals.
An approval cannot be claimed before the exact proposal is persisted.
"""
from __future__ import annotations
from contextlib import closing
from datetime import datetime, timezone
import json
import sqlite3
from .discord_approval_boundary import ApprovalPlan, TrustedDiscordEvent

class ProposalRegistry:
    def __init__(self, db):
        self.db=str(db)
    def initialize(self):
        with closing(sqlite3.connect(self.db,timeout=10)) as con, con:
            con.execute("""CREATE TABLE IF NOT EXISTS proposals(
                proposal_id TEXT PRIMARY KEY, digest TEXT NOT NULL,
                owner_id TEXT NOT NULL, channel_id TEXT NOT NULL,
                expires_at TEXT NOT NULL, state TEXT NOT NULL
                CHECK(state IN ('PENDING','APPROVED')))""")
            con.execute("""CREATE TABLE IF NOT EXISTS accepted_interactions(
                interaction_id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL UNIQUE,
                FOREIGN KEY(proposal_id) REFERENCES proposals(proposal_id))""")
    def register(self, plan: ApprovalPlan):
        if not plan.proposal_id or not plan.owner_id or not plan.channel_id or plan.expires_at.tzinfo is None:
            raise ValueError("invalid proposal")
        with closing(sqlite3.connect(self.db,timeout=10)) as con, con:
            existing=con.execute("SELECT digest,owner_id,channel_id,expires_at FROM proposals WHERE proposal_id=?",(plan.proposal_id,)).fetchone()
            fields=(plan.digest(),plan.owner_id,plan.channel_id,plan.expires_at.isoformat())
            if existing:
                if existing!=fields: raise ValueError("proposal conflict")
                return False
            con.execute("INSERT INTO proposals VALUES(?,?,?,?,?,?)",(plan.proposal_id,*fields,"PENDING"))
            return True
    def approve(self, plan: ApprovalPlan, event: TrustedDiscordEvent, *,
                submitted_hash: str, now: datetime | None=None) -> bool:
        from hmac import compare_digest
        now=now or datetime.now(timezone.utc)
        if (now.tzinfo is None or not event.signature_verified or
            not event.interaction_id or not event.actor_id or not event.channel_id):
            return False
        with closing(sqlite3.connect(self.db,timeout=10,isolation_level=None)) as con:
            try:
                con.execute("BEGIN IMMEDIATE")
                row=con.execute("SELECT digest,owner_id,channel_id,expires_at,state FROM proposals WHERE proposal_id=?",(plan.proposal_id,)).fetchone()
                if not row:
                    con.execute("ROLLBACK");return False
                digest,owner,channel,expiry,state=row
                valid=(state=="PENDING" and owner==event.actor_id and channel==event.channel_id
                       and compare_digest(digest,plan.digest())
                       and compare_digest(digest,submitted_hash)
                       and now < datetime.fromisoformat(expiry))
                if not valid:
                    con.execute("ROLLBACK");return False
                con.execute("INSERT INTO accepted_interactions VALUES(?,?)",(event.interaction_id,plan.proposal_id))
                con.execute("UPDATE proposals SET state='APPROVED' WHERE proposal_id=?",(plan.proposal_id,))
                con.execute("COMMIT")
                return True
            except (sqlite3.IntegrityError,ValueError,TypeError):
                con.execute("ROLLBACK")
                return False
