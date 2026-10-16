"""Bounded, read-only operational graph context supplied to Atlas's LLM.

The graph is telemetry/evidence, not a command source or causal explanation.
Never forwards raw prompts, user data, Discord content or credentials.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

_METRICS=("valencia","ativacao","estresse","confianca","engajamento","curiosidade")
def graph_context_for_llm(path,*,now=None,max_age_seconds=600):
    path=Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size>240000:
        return ()
    try:
        raw=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw,dict) or raw.get("schema_version")!=1:
            return ()
        series=raw.get("affect_series",[])
        if not isinstance(series,list) or len(series)>500:return ()
        states=[]
        for entry in series:
            if not isinstance(entry,dict) or entry.get("agent")!="atlas":continue
            values={}
            for key in _METRICS:
                value=entry.get(key)
                if type(value) not in (int,float) or not math.isfinite(value):
                    raise ValueError("bad affect telemetry")
                if not (-1<=value<=1 if key=="valencia" else 0<=value<=1):
                    raise ValueError("metric out of bounds")
                values[key]=round(float(value),3)
            timestamp=str(entry["at"])
            stamp=datetime.fromisoformat(timestamp.replace("Z","+00:00"))
            if stamp.tzinfo is None:raise ValueError("timestamp has no timezone")
            states.append((stamp,values))
            if len(states)==2:break
        if not states:return ()
        current_time=now or datetime.now(timezone.utc)
        age=(current_time-states[0][0]).total_seconds()
        if age< -120 or age>max_age_seconds:return ()
        items=[{"type":"atlas_affect_measurement","at":states[0][0].isoformat(),
             "metrics":states[0][1],
             "source":"operational_affective_graph",
             "interpretation":"synthetic_software_variables"}]
        if len(states)>1:
            delta={m:round(states[0][1][m]-states[1][1][m],3) for m in _METRICS}
            items.append({"type":"atlas_affect_change","delta":delta,
                          "causality":"unverified_temporal_association"})
        counts=raw.get("observed_events_by_severity") or {}
        if isinstance(counts,dict):
            clean={}
            for name in ("info","notice","warning","critical"):
                val=counts.get(name)
                if type(val) is int and 0<=val<=1000000:clean[name]=val
            if clean:items.append({"type":"observation_counts_historical","counts":clean,
                "warning":"counts_are_not_current_incidents"})
        # The graph can expose agent hierarchy without IDs containing usernames.
        nodes=raw.get("nodes") or []
        if isinstance(nodes,list):
            agents=[x["id"] for x in nodes if isinstance(x,dict) and x.get("type")=="agent"
                    and isinstance(x.get("id"),str) and x["id"].startswith("agent:")
                    and len(x["id"])<=85][:5]
            if agents:items.append({"type":"registered_agents","ids":agents})
        return tuple(items[:4])
    except (OSError,ValueError,TypeError,KeyError,UnicodeError):
        return ()
