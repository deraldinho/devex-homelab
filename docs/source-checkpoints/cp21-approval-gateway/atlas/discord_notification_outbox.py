"""Durable Discord delivery outbox (staging, no network calls)."""
import sqlite3
from contextlib import closing

class NotificationOutbox:
    def __init__(self, db):
        self.db = str(db)

    def initialize(self):
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("CREATE TABLE IF NOT EXISTS discord_outbox (proposal_id TEXT PRIMARY KEY, digest TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('PENDING','SENT')), message_id TEXT)")

    def enqueue(self, proposal_id, digest):
        if not proposal_id or not isinstance(digest, str) or len(digest) != 64:
            raise ValueError('invalid proposal')
        with closing(sqlite3.connect(self.db)) as c, c:
            previous = c.execute('SELECT digest FROM discord_outbox WHERE proposal_id=?', (proposal_id,)).fetchone()
            if previous:
                if previous[0] != digest:
                    raise ValueError('conflicting proposal')
                return False
            c.execute("INSERT INTO discord_outbox VALUES (?,?,'PENDING',NULL)", (proposal_id,digest))
            return True
    def pending(self):
        with closing(sqlite3.connect(self.db)) as c:
            return c.execute("SELECT proposal_id,digest FROM discord_outbox WHERE state='PENDING' ORDER BY proposal_id").fetchall()

    def mark_sent(self, proposal_id, digest, message_id):
        if not isinstance(message_id,str) or not message_id:
            return False
        with closing(sqlite3.connect(self.db)) as c, c:
            result=c.execute("UPDATE discord_outbox SET state='SENT',message_id=? WHERE proposal_id=? AND digest=? AND state='PENDING'",(message_id,proposal_id,digest))
            return result.rowcount==1
