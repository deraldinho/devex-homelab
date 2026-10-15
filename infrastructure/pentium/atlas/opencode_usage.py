"""Validated token/cost telemetry from OpenCode session responses."""
import math

def extract_usage(state):
    if not isinstance(state,dict):return None
    tokens=state.get("tokens")
    if not isinstance(tokens,dict):tokens={}
    cache=tokens.get("cache")
    if not isinstance(cache,dict):cache={}
    fields={"input":tokens.get("input"),"output":tokens.get("output"),
            "reasoning":tokens.get("reasoning"),
            "cache_read":cache.get("read"),"cache_write":cache.get("write")}
    cleaned={key:(value if type(value) is int and value>=0 else None)
             for key,value in fields.items()}
    cost=state.get("cost")
    if type(cost) in (int,float) and math.isfinite(cost) and cost>=0:
        cleaned["cost"]=float(cost)
    else:cleaned["cost"]=None
    if all(x is None for x in cleaned.values()):return None
    cleaned["source"]="opencode-session"
    return cleaned
