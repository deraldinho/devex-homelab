"""Fail-closed inventory parser: catalog listing is not proof of free access."""
from __future__ import annotations
import json
from atlas_model_ranker import ModelProfile

def build_profiles(model_ids, verified_zero_cost, measurements=None):
    """verified_zero_cost is trusted operator/provider metadata, not an agent claim."""
    measurements=measurements or {}
    profiles=[]
    for full in sorted(set(model_ids)):
        if not isinstance(full,str) or "/" not in full: continue
        provider,model=full.split("/",1)
        if provider!="opencode" or model not in verified_zero_cost: continue
        entry=verified_zero_cost[model]
        if not isinstance(entry,dict): continue
        if entry.get("input_price") != 0 or entry.get("output_price") != 0 or entry.get("verified") is not True:
            continue
        metric=measurements.get(model,{})
        if not isinstance(metric,dict): metric={}
        capabilities=entry.get("capabilities",())
        if not isinstance(capabilities,(list,tuple,set,frozenset)): continue
        profiles.append(ModelProfile(model,0,0,True,frozenset(capabilities),
            float(metric.get("quality",0)),float(metric.get("latency_ms",10000)),
            metric.get("quota_remaining",True) is True,metric.get("cooldown",False) is True))
    return profiles

def summarize_usage(attempts):
    """Aggregate only provider-reported usage; missing values stay unknown."""
    total={"input_tokens":0,"output_tokens":0,"cache_read_tokens":0}
    seen=0
    for item in attempts:
        usage=item.get("usage") if isinstance(item,dict) else None
        if not isinstance(usage,dict): continue
        if not all(type(usage.get(k)) is int and usage[k]>=0 for k in total):continue
        for k in total:total[k]+=usage[k]
        seen+=1
    return {"samples":seen,**total}
