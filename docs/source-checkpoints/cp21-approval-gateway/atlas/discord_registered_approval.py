"""Fail-closed durable approval API bound only to persisted proposals."""
from __future__ import annotations
from contextlib import closing
from datetime import datetime, timezone
import hmac
import sqlite3
from .proposal_registry import ProposalRegistry
from .discord_interaction_intake import parse_verified_interaction

def approve_registered_interaction(*, registry: ProposalRegistry,
        proposal_id: str, submitted_hash: str, public_key_hex: str,
        signature_hex: str, timestamp: str, raw_body: bytes,
        now: datetime | None = None) -> bool:
    event = parse_verified_interaction(public_key_hex=public_key_hex,
        signature_hex=signature_hex,timestamp=timestamp,raw_body=raw_body,now=now)
    now = now or datetime.now(timezone.utc)
    if event is None or now.tzinfo is None or not proposal_id:
        return False
    with closing(sqlite3.connect(registry.db,timeout=10,isolation_level=None)) as con:
        try:
            con.execute("BEGIN IMMEDIATE")
            row=con.execute("SELECT digest,owner_id,channel_id,expires_at,state FROM proposals WHERE proposal_id=?",
                            (proposal_id,)).fetchone()
            if row is None:
                con.execute("ROLLBACK");return False
            digest,owner,channel,expires,state=row
            expiration=datetime.fromisoformat(expires)
            valid=(state=="PENDING" and event.actor_id==owner and event.channel_id==channel
                   and expiration.tzinfo is not None and now<expiration
                   and isinstance(submitted_hash,str) and hmac.compare_digest(submitted_hash,digest))
            if not valid:
                con.execute("ROLLBACK");return False
            con.execute("INSERT INTO accepted_interactions(interaction_id,proposal_id) VALUES (?,?)",
                        (event.interaction_id,proposal_id))
            con.execute("UPDATE proposals SET state='APPROVED' WHERE proposal_id=?",(proposal_id,))
            con.execute("COMMIT")
            return True
        except (sqlite3.IntegrityError,ValueError,TypeError):
            con.execute("ROLLBACK")
            return False
