"""Durable delivery attempts and dead-letter tracking for Discord outbox.
Does not perform HTTP requests or mutate existing discord_outbox schemas.
"""
from contextlib import closing
import sqlite3
import time

class DeliveryLedger:
    def __init__(self,db,clock=time.time,max_attempts=5):
        if max_attempts < 1: raise ValueError("invalid attempts")
        self.db=str(db);self.clock=clock;self.max_attempts=max_attempts
    def initialize(self):
        with closing(sqlite3.connect(self.db)) as c,c:
            c.execute("""CREATE TABLE IF NOT EXISTS delivery_attempts(
              proposal_id TEXT PRIMARY KEY, attempts INTEGER NOT NULL DEFAULT 0,
              next_at REAL NOT NULL DEFAULT 0, state TEXT NOT NULL DEFAULT 'READY'
              CHECK(state IN ('READY','LEASED','DEAD','ACKED')),
              lease_until REAL NOT NULL DEFAULT 0)""")
    def track(self,proposal_id):
        with closing(sqlite3.connect(self.db)) as c,c:
            c.execute("INSERT OR IGNORE INTO delivery_attempts(proposal_id) VALUES(?)",(proposal_id,))
    def acquire(self,proposal_id,lease_seconds=30):
        now=self.clock()
        with closing(sqlite3.connect(self.db,timeout=10,isolation_level=None)) as c:
            try:
                c.execute("BEGIN IMMEDIATE")
                r=c.execute("SELECT attempts,next_at,state,lease_until FROM delivery_attempts WHERE proposal_id=?",(proposal_id,)).fetchone()
                if not r or r[2] in ('DEAD','ACKED') or now<r[1] or (r[2]=='LEASED' and now<r[3]):
                    c.execute("ROLLBACK");return False
                c.execute("UPDATE delivery_attempts SET state='LEASED',lease_until=? WHERE proposal_id=?",(now+lease_seconds,proposal_id))
                c.execute("COMMIT");return True
            except Exception:
                if c.in_transaction:c.execute("ROLLBACK")
                raise
    def failed(self,proposal_id):
        now=self.clock()
        with closing(sqlite3.connect(self.db)) as c,c:
            row=c.execute("SELECT attempts,state FROM delivery_attempts WHERE proposal_id=?",(proposal_id,)).fetchone()
            if not row or row[1]!='LEASED':return False
            count=row[0]+1
            state='DEAD' if count>=self.max_attempts else 'READY'
            delay=min(3600,30*2**min(count-1,7))
            c.execute("UPDATE delivery_attempts SET attempts=?,state=?,next_at=?,lease_until=0 WHERE proposal_id=?",(count,state,now+delay,proposal_id))
            return True
    def ack(self,proposal_id):
        with closing(sqlite3.connect(self.db)) as c,c:
            return c.execute("UPDATE delivery_attempts SET state='ACKED',lease_until=0 WHERE proposal_id=? AND state='LEASED'",(proposal_id,)).rowcount==1
    def status(self,proposal_id):
        with closing(sqlite3.connect(self.db)) as c:
            return c.execute("SELECT state,attempts FROM delivery_attempts WHERE proposal_id=?",(proposal_id,)).fetchone()
