"""Atlas operational-affective temporal graph: auditable *simulated* state.

Separate from semantic MemoryGraph. Events represent observations, not proven
causal effects; numeric affect readings are software variables, not sentience.
No raw chat, service payloads, credentials or untrusted descriptions are stored.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType

_METRICS=("valencia","ativacao","estresse","confianca","engajamento","curiosidade")
_LABEL=re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_KINDS={"atlas","agent","task","entity","stimulus","affect_snapshot"}
_RELATIONS={"SUPERVISES","DELEGATED_TO","WORKS_ON","OBSERVED","CONCERNS","HAS_SNAPSHOT",
            "PRECEDES","OBSERVED_DURING","INHERITS_CONTEXT"}
_SEVERITIES={"info","notice","warning","critical"}
def _utc(text):
    if not isinstance(text,str):raise ValueError("timestamp invalid")
    dt=datetime.fromisoformat(text.replace("Z","+00:00"))
    if dt.tzinfo is None or dt.utcoffset() is None:raise ValueError("timezone required")
    return dt.astimezone(timezone.utc).isoformat()
def _id(name):
    if not isinstance(name,str) or not _LABEL.fullmatch(name):
        raise ValueError("unsafe identity")
    return name
def _sha(raw):
    return hashlib.sha256(str(raw).encode("utf-8")).hexdigest()[:24]
def _metric_values(values):
    if not isinstance(values,dict):raise ValueError("affective state invalid")
    clean={}
    for key in _METRICS:
        number=values.get(key)
        if isinstance(number,bool) or not isinstance(number,(int,float)) or not math.isfinite(number):
            raise ValueError("invalid affective metric")
        low=-1.0 if key=="valencia" else 0.0
        if not low<=number<=1.0:raise ValueError("metric outside validated range")
        clean[key]=float(number)
    return clean

@dataclass(frozen=True)
class AgentAffectiveEnvelope:
    """Immutable observational context; not a shared emotion or safety authority."""
    agent_id: str
    parent_id: str
    task_id: str
    snapshot_id: str
    generated_at: str
    metrics: dict[str,float]
    schema_version: int = 1

    def __post_init__(self):
        _id(self.agent_id);_id(self.parent_id);_id(self.task_id);_id(self.snapshot_id)
        _utc(self.generated_at)
        if self.schema_version!=1:raise ValueError("invalid envelope schema")
        object.__setattr__(self,"metrics",MappingProxyType(_metric_values(self.metrics)))

class OperationalAffectiveGraph:
    def __init__(self,path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        if self.path.is_symlink():raise ValueError("graph symlink prohibited")
        with self._db() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY, kind TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS edges (
                    source_id TEXT NOT NULL, target_id TEXT NOT NULL,
                    relation TEXT NOT NULL, event_key TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    PRIMARY KEY(source_id,target_id,relation,event_key),
                    FOREIGN KEY(source_id) REFERENCES nodes(node_id),
                    FOREIGN KEY(target_id) REFERENCES nodes(node_id)
                );
                CREATE INDEX IF NOT EXISTS idx_graph_edges_time ON edges(observed_at);
                CREATE TABLE IF NOT EXISTS events (
                    event_key TEXT PRIMARY KEY, source TEXT NOT NULL, kind TEXT NOT NULL,
                    severity TEXT NOT NULL, observed_at TEXT NOT NULL,
                    correlation_key TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS affect_samples (
                    sample_key TEXT PRIMARY KEY, agent_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    valencia REAL NOT NULL, ativacao REAL NOT NULL,
                    estresse REAL NOT NULL, confianca REAL NOT NULL,
                    engajamento REAL NOT NULL, curiosidade REAL NOT NULL,
                    provenance TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_affect_agent_time ON affect_samples(agent_id,updated_at);
            """)
            self._node(conn,"atlas","atlas","bootstrap")
    @contextmanager
    def _db(self):
        connection=sqlite3.connect(self.path,timeout=5)
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")
            with connection:yield connection
        finally:
            connection.close()
    @staticmethod
    def _node(conn,node_id,kind,when):
        _id(node_id)
        if kind not in _KINDS:raise ValueError("unknown node kind")
        conn.execute("INSERT OR IGNORE INTO nodes VALUES(?,?,?)",(node_id,kind,when))
    @staticmethod
    def _edge(conn,source,target,relation,event_key,when):
        if relation not in _RELATIONS:raise ValueError("invalid relation")
        conn.execute("INSERT OR IGNORE INTO edges VALUES(?,?,?,?,?)",
                     (source,target,relation,event_key,when))
    def record_stimulus(self,event):
        """Record only allowlisted labels. Raw 'payload' is intentionally discarded."""
        if not isinstance(event,dict):raise ValueError("invalid stimulus")
        source=_id(event["source"]);kind=_id(event["kind"])
        severity=event.get("severity")
        if severity not in _SEVERITIES:raise ValueError("invalid severity")
        when=_utc(event["timestamp"])
        raw_id=event.get("stimulus_id")
        if not isinstance(raw_id,str) or not raw_id or len(raw_id)>256:
            raise ValueError("invalid stimulus identifier")
        key="event:"+_sha(raw_id)
        correlation="corr:"+_sha(event.get("correlation_id") or raw_id)
        node="stimulus:"+_sha(raw_id)
        target="entity:"+_sha(event.get("entity_id") or source)
        with self._db() as db:
            self._node(db,node,"stimulus",when)
            self._node(db,target,"entity",when)
            db.execute("INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?)",
                       (key,source,kind,severity,when,correlation))
            self._edge(db,"atlas",node,"OBSERVED",key,when)
            self._edge(db,node,target,"CONCERNS",key,when)
        return key
    def record_affect(self,agent_id,state,*,source_stimulus_id=None,provenance="affective-engine"):
        """State comes only from validated engine output; no inference about feelings."""
        agent_id=_id(agent_id)
        _id(provenance)
        metrics=_metric_values(state)
        when=_utc(state["atualizado_em"])
        sample_key="affect:"+_sha(agent_id+":"+when+":"+json.dumps(metrics,sort_keys=True))
        anchor="atlas" if agent_id=="atlas" else "agent:"+agent_id
        with self._db() as db:
            if agent_id!="atlas":
                known=db.execute("SELECT 1 FROM nodes WHERE node_id=? AND kind='agent'",(anchor,)).fetchone()
                if not known:raise ValueError("unknown child agent")
            old=db.execute("SELECT sample_key FROM affect_samples WHERE agent_id=? ORDER BY updated_at DESC LIMIT 1",
                           (agent_id,)).fetchone()
            self._node(db,sample_key,"affect_snapshot",when)
            db.execute("""INSERT OR IGNORE INTO affect_samples
                (sample_key,agent_id,updated_at,valencia,ativacao,estresse,confianca,engajamento,curiosidade,provenance)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (sample_key,agent_id,when,*(metrics[k] for k in _METRICS),provenance))
            self._edge(db,anchor,sample_key,"HAS_SNAPSHOT",sample_key,when)
            if old and old[0]!=sample_key:
                self._edge(db,old[0],sample_key,"PRECEDES",sample_key,when)
            if source_stimulus_id:
                event_id="stimulus:"+_sha(source_stimulus_id)
                if db.execute("SELECT 1 FROM nodes WHERE node_id=?",(event_id,)).fetchone():
                    self._edge(db,event_id,sample_key,"OBSERVED_DURING",sample_key,when)
        return sample_key
    def delegate(self,agent_id,task_id,*,parent_id="atlas",time_iso=None):
        """Inherit a *copy* of observational context, not authority or mutable state."""
        _id(agent_id);_id(parent_id);_id(task_id)
        if agent_id=="atlas" or parent_id==agent_id:raise ValueError("invalid hierarchy")
        when=_utc(time_iso or datetime.now(timezone.utc).isoformat())
        parent="atlas" if parent_id=="atlas" else "agent:"+parent_id
        agent="agent:"+agent_id;task="task:"+task_id
        with self._db() as db:
            if not db.execute("SELECT 1 FROM nodes WHERE node_id=?",(parent,)).fetchone():
                raise ValueError("parent not registered")
            existing=db.execute("SELECT 1 FROM nodes WHERE node_id=?",(agent,)).fetchone()
            if existing:raise ValueError("child agent already exists")
            last=db.execute("""SELECT sample_key,updated_at,valencia,ativacao,estresse,
                               confianca,engajamento,curiosidade FROM affect_samples
                               WHERE agent_id=? ORDER BY updated_at DESC LIMIT 1""",
                            (parent_id,)).fetchone()
            if not last:raise ValueError("no measured parent state; cannot fabricate context")
            self._node(db,agent,"agent",when)
            self._node(db,task,"task",when)
            delegation="delegation:"+_sha(agent_id+":"+task_id)
            self._edge(db,parent,agent,"SUPERVISES",delegation,when)
            self._edge(db,parent,task,"DELEGATED_TO",delegation,when)
            self._edge(db,agent,task,"WORKS_ON",delegation,when)
            self._edge(db,agent,last[0],"INHERITS_CONTEXT",delegation,when)
            metrics=dict(zip(_METRICS,last[2:]))
        return AgentAffectiveEnvelope(agent_id,parent_id,task_id,last[0],when,metrics)
    def export(self,*,limit=200):
        if not isinstance(limit,int) or not 1<=limit<=500:raise ValueError("bounded export only")
        with self._db() as db:
            ns=db.execute("SELECT node_id,kind FROM nodes ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall()
            links=db.execute("SELECT source_id,target_id,relation,observed_at FROM edges ORDER BY observed_at DESC LIMIT ?",(limit,)).fetchall()
            samples=db.execute("""SELECT sample_key,agent_id,updated_at,valencia,ativacao,
                    estresse,confianca,engajamento,curiosidade,provenance
                    FROM affect_samples ORDER BY updated_at DESC LIMIT ?""",(limit,)).fetchall()
            alerts=db.execute("""SELECT severity,COUNT(*) FROM events
                 GROUP BY severity ORDER BY severity""").fetchall()
        ordered=list(reversed([row for row in samples if row[1]=="atlas"]))
        transitions=[]
        for previous,current in zip(ordered,ordered[1:]):
            delta={name:round(current[3+i]-previous[3+i],6) for i,name in enumerate(_METRICS)}
            linked=[edge["source"] for edge in
                    ({"source":src,"target":target,"type":rel} for src,target,rel,_at in links)
                    if edge["target"]==current[0] and edge["type"]=="OBSERVED_DURING"]
            transitions.append({"from":previous[0],"to":current[0],"at":current[2],
                "delta":delta,"observed_with":linked,
                "causality":"unverified_temporal_association"})
        return {"schema_version":1,
            "nodes":[{"id":a,"type":b} for a,b in ns],
            "edges":[{"source":a,"target":b,"type":c,"at":d} for a,b,c,d in links],
            "affect_series":[dict(zip(("id","agent","at",*_METRICS,"provenance"),x)) for x in samples],
            "observed_events_by_severity":dict(alerts),
            "affect_transitions":transitions,
            "interpretation":"synthetic_state_metrics_not_subjective_emotions"}
