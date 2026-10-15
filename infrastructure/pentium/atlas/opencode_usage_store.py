"""Idempotent SQLite accounting; stores metadata, never prompts or responses."""
import sqlite3
from contextlib import closing

class InferenceUsageStore:
    def __init__(self,path):
        self.path=str(path)
    def initialize(self):
        with closing(sqlite3.connect(self.path)) as c,c:
            c.execute("""CREATE TABLE IF NOT EXISTS inference_usage(
                provider TEXT NOT NULL, session_id TEXT NOT NULL,
                model TEXT NOT NULL, tokens_input INTEGER,
                tokens_output INTEGER, tokens_cache_read INTEGER,
                cost_usd REAL, duration_ms INTEGER NOT NULL,
                success INTEGER NOT NULL,
                PRIMARY KEY(provider,session_id))""")
    def record(self,event):
        provider,model,sid=(event.get(k) for k in ("provider","model","session_id"))
        if not all(isinstance(x,str) and x for x in (provider,model,sid)):
            return False  # no reliable session identity: don't inflate totals
        counters=[]
        for key in ("tokens_input","tokens_output","tokens_cache_read"):
            n=event.get(key)
            if n is not None and (type(n) is not int or n<0):
                raise ValueError("invalid token count")
            counters.append(n)
        cost=event.get("cost_usd")
        if cost is not None and (type(cost) not in (int,float) or cost<0):
            raise ValueError("invalid cost")
        duration=event.get("duration_ms")
        if type(duration) is not int or duration<0:raise ValueError("invalid duration")
        success=event.get("success")
        if type(success) is not bool:raise ValueError("invalid outcome")
        value=(model,*counters,cost,int(success))
        with closing(sqlite3.connect(self.path,timeout=10)) as c,c:
            prior=c.execute("""SELECT model,tokens_input,tokens_output,
                tokens_cache_read,cost_usd,success FROM inference_usage
                WHERE provider=? AND session_id=?""",(provider,sid)).fetchone()
            if prior is not None:
                if prior!=value:raise ValueError("conflicting usage for session")
                return False
            c.execute("""INSERT INTO inference_usage VALUES (?,?,?,?,?,?,?,?,?)""",
                (provider,sid,model,*counters,cost,duration,int(success)))
            return True
    def summary(self):
        with closing(sqlite3.connect(self.path)) as c:
            return c.execute("""SELECT COUNT(*),COALESCE(SUM(tokens_input),0),
                COALESCE(SUM(tokens_output),0),
                COALESCE(SUM(tokens_cache_read),0),
                COALESCE(SUM(cost_usd),0) FROM inference_usage""").fetchone()
