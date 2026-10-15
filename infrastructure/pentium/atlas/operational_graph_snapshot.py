"""Safe read-only projection of live Atlas observations into its temporal graph.

The existing observation daemon remains the source of truth. This sampler
does not start, stop, or control agents and never reads raw chat payloads.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .operational_affective_graph import OperationalAffectiveGraph

DEFAULT_RUNTIME=Path.home()/"pentium-agent"/"atlas"/"runtime"
def _json(path):
    p=Path(path)
    if not p.is_file() or p.is_symlink():raise ValueError("source missing or symlink")
    if p.stat().st_size>131072:raise ValueError("oversized runtime context")
    doc=json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(doc,dict):raise ValueError("invalid runtime context")
    return doc

def ingest_current(graph,*,runtime=DEFAULT_RUNTIME):
    """Returns counts; raw payloads, people and chat never enter graph."""
    runtime=Path(runtime)
    context=_json(runtime/"cognitive-observation-context.json")
    saved=_json(runtime/"affective-state.json")
    if saved.get("versao_esquema")!=1:raise ValueError("unknown affective schema")
    changes=context.get("recent_changes") or []
    if not isinstance(changes,list) or len(changes)>64:raise ValueError("unbounded changes")
    accepted=0;rejected=0
    for change in changes:
        try:
            graph.record_stimulus(change)
            accepted+=1
        except (ValueError,TypeError,KeyError):
            rejected+=1
    state=saved["estado"]
    correlation=context.get("source_stimulus_id")
    # Only link a stimulus to an affective snapshot inside a narrow time window.
    if not isinstance(correlation,str):correlation=None
    try:
        stamp=datetime.fromisoformat(state["atualizado_em"].replace("Z","+00:00"))
        newest=datetime.fromisoformat(context["generated_at"].replace("Z","+00:00"))
        if stamp.tzinfo is None or newest.tzinfo is None or abs((stamp-newest).total_seconds())>120:
            correlation=None
    except (TypeError,KeyError,ValueError):
        correlation=None
    graph.record_affect("atlas",state,source_stimulus_id=correlation)
    return {"accepted_observations":accepted,"rejected_observations":rejected,
            "correlation_linked":bool(correlation)}

def publish_graph(graph,destination,*,limit=200):
    """Expose bounded, sanitized JSON for a local visualization/UI."""
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    payload=graph.export(limit=limit)
    tmp=destination.with_name(destination.name+".tmp")
    flags=os.O_CREAT|os.O_EXCL|os.O_WRONLY
    fd=os.open(tmp,flags,0o600)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump(payload,f,ensure_ascii=False,sort_keys=True,separators=(",",":"))
            f.write("\n")
            f.flush();os.fsync(f.fileno())
        os.replace(tmp,destination)
    finally:
        tmp.unlink(missing_ok=True)
    if os.name=="posix":os.chmod(destination,0o600)
    return {"nodes":len(payload["nodes"]),"edges":len(payload["edges"]),
            "affect_samples":len(payload["affect_series"])}

def main(argv=None):
    parser=argparse.ArgumentParser(description="Record safe Atlas affective operations graph")
    parser.add_argument("--runtime",type=Path,default=DEFAULT_RUNTIME)
    parser.add_argument("--graph",type=Path,default=DEFAULT_RUNTIME/"operational-affective-graph.sqlite3")
    parser.add_argument("--export",type=Path,default=DEFAULT_RUNTIME/"operational-affective-graph.json")
    args=parser.parse_args(argv)
    graph=OperationalAffectiveGraph(args.graph)
    result=ingest_current(graph,runtime=args.runtime)
    result.update(publish_graph(graph,args.export))
    print("ATLAS_TEMPORAL_GRAPH",result)
    return 0
if __name__=="__main__":
    raise SystemExit(main())
