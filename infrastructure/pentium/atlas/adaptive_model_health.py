"""Adaptive free-model feedback: durable, redacted, and fail-closed.

Observed outcomes complement (never override) the existing verified-zero-cost gate.
Unknown quota != unlimited quota. No prompts, keys, or response text are persisted.
"""
from __future__ import annotations
import math
import re
from contextlib import contextmanager
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class ModelSignal:
    provider: str
    model: str
    success: bool
    latency_ms: int | None
    error: str | None = None
    quota_remaining: int | None = None
    observed_at: float = 0.0
    event_id: str | None = None

class AdaptiveModelHealth:
    def __init__(self, path, *, now=time.time, ttl_seconds=86400):
        self.path=Path(path)
        self.now=now
        self.ttl_seconds=ttl_seconds
        if ttl_seconds<=0:raise ValueError("ttl must be positive")
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS signals(
                id INTEGER PRIMARY KEY,
                provider TEXT NOT NULL, model TEXT NOT NULL,
                success INTEGER NOT NULL, latency_ms INTEGER,
                error TEXT, quota_remaining INTEGER, observed_at REAL NOT NULL,
                event_id TEXT
            )""")
            columns={row[1] for row in db.execute("PRAGMA table_info(signals)")}
            if "event_id" not in columns:
                db.execute("ALTER TABLE signals ADD COLUMN event_id TEXT")
            db.execute("CREATE INDEX IF NOT EXISTS signals_latest ON signals(provider,model,observed_at)")
            db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS signals_event_id
                ON signals(provider,model,event_id) WHERE event_id IS NOT NULL""")
            db.execute("""CREATE TABLE IF NOT EXISTS quality_evaluations(
                provider TEXT NOT NULL, model TEXT NOT NULL, task TEXT NOT NULL,
                evaluation_id TEXT NOT NULL, passed INTEGER NOT NULL,
                observed_at REAL NOT NULL,
                PRIMARY KEY(provider,model,task,evaluation_id)
            )""")
    @contextmanager
    def _connect(self):
        db=sqlite3.connect(self.path,timeout=4)
        try:
            db.execute("PRAGMA busy_timeout=4000")
            with db:
                yield db
        finally:
            db.close()
    def record(self, signal:ModelSignal):
        if not isinstance(signal,ModelSignal):raise TypeError("invalid signal")
        if not signal.provider or not signal.model:raise ValueError("invalid identity")
        if signal.latency_ms is not None and (not isinstance(signal.latency_ms,int) or signal.latency_ms<0):
            raise ValueError("invalid latency")
        if signal.quota_remaining is not None and (not isinstance(signal.quota_remaining,int) or signal.quota_remaining<0):
            raise ValueError("invalid quota")
        if signal.error not in (None,"unavailable","rate_limit","timeout","auth","invalid_model","quota_exhausted"):
            raise ValueError("invalid error category")
        if signal.event_id is not None and not re.fullmatch(r"[A-Za-z0-9_.:-]{1,150}",signal.event_id):
            raise ValueError("invalid opaque event id")
        ts=float(signal.observed_at or self.now())
        if not math.isfinite(ts) or ts>self.now()+120:raise ValueError("invalid timestamp")
        with self._connect() as db:
            db.execute("""INSERT OR IGNORE INTO signals
                (provider,model,success,latency_ms,error,quota_remaining,observed_at,event_id)
                VALUES (?,?,?,?,?,?,?,?)""",
                (signal.provider,signal.model,int(signal.success),signal.latency_ms,signal.error,
                 signal.quota_remaining,ts,signal.event_id))
            db.execute("DELETE FROM signals WHERE observed_at < ?",(self.now()-30*86400,))
    def stats(self,provider,model):
        cutoff=self.now()-self.ttl_seconds
        with self._connect() as db:
            rows=db.execute("""SELECT success,latency_ms,error,quota_remaining,observed_at
                FROM signals WHERE provider=? AND model=? AND observed_at>=?
                ORDER BY observed_at DESC,id DESC LIMIT 40""",(provider,model,cutoff)).fetchall()
        if not rows:return {"samples":0,"success_rate":None,"latency_ms":None,
                            "cooldown":False,"quota_remaining":None,"quota_status":"unknown"}
        latencies=[x[1] for x in rows if x[0] and x[1] is not None]
        newest=rows[0]
        # A 429 is provider/model signal, but stale 429 must self-heal.
        cooldown=bool(newest[2] in ("rate_limit","quota_exhausted") and
                      self.now()-newest[4]<3600)
        quota=next((r[3] for r in rows if r[3] is not None),None)
        quota_status="exhausted" if newest[2]=="quota_exhausted" or quota==0 else (
            "measured" if quota is not None else "unknown")
        return {"samples":len(rows),"success_rate":sum(r[0] for r in rows)/len(rows),
                "latency_ms":sum(latencies)/len(latencies) if latencies else None,
                "cooldown":cooldown,"quota_remaining":quota,"quota_status":quota_status}
    def record_evaluation(self,provider,model,task,evaluation_id,passed):
        """Store only independently graded success/failure; never prompts or answers."""
        if not all(isinstance(x,str) and 1<=len(x)<=150 for x in (provider,model,task,evaluation_id)):
            raise ValueError("invalid evaluation identity")
        if not isinstance(passed,bool):raise ValueError("evaluation must be independently graded boolean")
        with self._connect() as db:
            db.execute("""INSERT OR IGNORE INTO quality_evaluations
                (provider,model,task,evaluation_id,passed,observed_at) VALUES(?,?,?,?,?,?)""",
                (provider,model,task,evaluation_id,int(passed),self.now()))
    def quality(self,provider,model,task):
        with self._connect() as db:
            passed,count=db.execute("""SELECT SUM(passed),COUNT(*) FROM quality_evaluations
                WHERE provider=? AND model=? AND task=? AND observed_at>=?""",
                (provider,model,task,self.now()-30*86400)).fetchone()
        return (passed/count,count) if count else (None,0)
    def rank(self,offers,*,task):
        """Reorder already authorized/eligible offers only; never admit new models."""
        # Only the upstream verified-free selector can admit candidates.
        candidates=[offer for offer in offers if not (
            (state:=self.stats(offer.provider,offer.model))["cooldown"]
            or state["quota_status"]=="exhausted"
        )]
        if not candidates:return ()
        def score(pair):
            idx,offer=pair
            stats=self.stats(offer.provider,offer.model)
            quality,q_count=self.quality(offer.provider,offer.model,task)
            # Quality only counts after >=3 independently graded task cases.
            grade=-(quality or 0) if q_count>=3 else 0
            reliability=(stats["success_rate"]*stats["samples"]+2)/(stats["samples"]+2) if stats["samples"] else 0
            latency=stats["latency_ms"] if stats["latency_ms"] is not None else 10000
            # Measured quality first, then observed reliability and latency.
            # Missing evidence remains neutral, original verified-free order breaks ties.
            return (grade,-round(reliability,3),round(latency/5000,2),idx)
        return tuple(offer for _,offer in sorted(enumerate(candidates),key=score))
    def observe_result(self,offer,result):
        from .modelo_llm_gateway import ErroInferencia
        error=None
        if not result.sucesso:
            if result.erro==ErroInferencia.MODELO_INDISPONIVEL:error="unavailable"
            elif result.erro==ErroInferencia.TIMEOUT:error="timeout"
            elif result.erro==ErroInferencia.BACKEND_INDISPONIVEL:error="unavailable"
            else:return
        self.record(ModelSignal(offer.provider,offer.model,bool(result.sucesso),
           result.duracao_ms if result.duracao_ms>=0 else None,error,
           event_id=result.session_id))
