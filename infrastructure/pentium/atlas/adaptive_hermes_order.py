"""Opt-in adaptive Hermes fallback ordering; reads metadata only.

Catalog checks are GET-only. Never send inference prompts or incur inference costs.
Preserves principal provider/model and every configured fallback.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import json
import sqlite3
import time
from pathlib import Path
from urllib import request,error
from .adaptive_model_health import AdaptiveModelHealth
from .hermes_fallback_expansion import replace_fallback_yaml,atomic_backup_and_write

NOUS_FREE_URL="https://portal.nousresearch.com/api/nous/recommended-models"
NVIDIA_MODELS_URL="https://integrate.api.nvidia.com/v1/models"

def read_catalogs(auth_path, *, fetch=None):
    """Return (Nous free IDs, NVIDIA model IDs), or None on any failed check."""
    def default_fetch(url,headers):
        req=request.Request(url,headers=headers)
        with request.urlopen(req,timeout=12) as resp:
            if resp.status!=200:raise OSError("catalog unavailable")
            return json.load(resp)
    fetch=fetch or default_fetch
    nous=fetch(NOUS_FREE_URL,{"Accept":"application/json"})
    if not isinstance(nous,dict) or not isinstance(nous.get("freeRecommendedModels"),list):
        raise ValueError("Nous catalog lacks free recommendations")
    allowed_nous=set()
    for item in nous["freeRecommendedModels"]:
        if not isinstance(item,dict):continue
        key=item.get("modelName") or item.get("model") or item.get("id")
        if isinstance(key,str) and key.endswith(":free"):allowed_nous.add(key)
    pool=json.loads(Path(auth_path).read_text(encoding="utf-8")).get("credential_pool",{}).get("nvidia",[])
    if not isinstance(pool,list):raise ValueError("invalid credential pool")
    available=[entry for entry in pool if isinstance(entry,dict)
        and isinstance(entry.get("access_token"),str)
        and entry["access_token"].startswith("nvapi-")]
    if not available:raise ValueError("NVIDIA credential not available")
    available.sort(key=lambda item:item.get("priority",100))
    nvidia=None
    for entry in available:
        try:
            nvidia=fetch(NVIDIA_MODELS_URL,{"Accept":"application/json",
                 "Authorization":"Bearer "+entry["access_token"]})
            break
        except error.HTTPError as exc:
            # Rotate credential used for catalog only; never expose the key or body.
            if exc.code not in (401,403,429):raise
    if not isinstance(nvidia,dict) or not isinstance(nvidia.get("data"),list):
        raise ValueError("NVIDIA model catalog unavailable")
    ids={x["id"] for x in nvidia["data"] if isinstance(x,dict) and isinstance(x.get("id"),str)}
    if not ids or not allowed_nous:raise ValueError("empty catalog: no rollout")
    return allowed_nous,ids

def read_hermes_usage(state_path,*,now=None):
    """Only aggregate activity counts; token totals are not a quality score."""
    path=Path(state_path)
    if not path.exists():return {}
    now=now if now is not None else time.time()
    with closing(sqlite3.connect(f"file:{path}?mode=ro",uri=True,timeout=5)) as db:
        rows=db.execute("""SELECT billing_provider,model,SUM(api_call_count)
            FROM session_model_usage WHERE last_seen>=? AND api_call_count>0
            GROUP BY billing_provider,model""",(now-7*86400,)).fetchall()
    return {(p,m):int(n) for p,m,n in rows if isinstance(p,str) and isinstance(m,str)}

def adaptive_order(entries, *, catalog, health, usage=None, task="general"):
    """Fail-closed admission: no model may be inserted, no primary is touched."""
    if not isinstance(entries,list) or not all(isinstance(x,dict) for x in entries):
        raise ValueError("invalid fallback list")
    nous,nvidia=catalog
    seen=set()
    for x in entries:
        identity=(x.get("provider"),x.get("model"))
        if identity in seen or identity[0] not in ("nous","nvidia") or not isinstance(identity[1],str):
            raise ValueError("unmanaged or duplicated fallback")
        seen.add(identity)
    usage=usage or {}
    def key(pair):
        index,x=pair
        provider,model=x["provider"],x["model"]
        live=model in (nous if provider=="nous" else nvidia)
        stats=health.stats(provider,model)
        quality,count=health.quality(provider,model,task)
        # Never infer quota from a model appearing in a catalog.
        block=stats["cooldown"] or stats["quota_status"]=="exhausted"
        # Avoid flapping: quality needs 3 graded tasks; speed/reliability need 3 actual calls.
        quality_level=-(quality or 0) if count>=3 else 0
        samples=stats["samples"]
        success_level=-(stats["success_rate"] or 0) if samples>=3 else 0
        latency=stats["latency_ms"] if samples>=3 and stats["latency_ms"] is not None else 0
        # Session usage is a tiny stable tie-breaker, never treated as proof of success.
        observations=usage.get((provider,model),0)
        activity=-min(observations,30) if observations>=3 else 0
        return (0 if provider=="nous" else 1,not live,block,
                quality_level,success_level,round(latency/1000,1),activity,index)
    return [x for _,x in sorted(enumerate(entries),key=key)]

def plan(config_text,manifest,catalog,health,usage):
    import yaml
    parsed=yaml.safe_load(config_text)
    if not isinstance(parsed,dict) or not isinstance(parsed.get("model"),dict):
        raise ValueError("invalid Hermes config")
    if parsed["model"].get("provider")!="nous":
        raise ValueError("unexpected primary provider")
    entries=parsed.get("fallback_providers",[])
    valid={("nous",m) for m in manifest.get("nous_free",[])}
    valid|={("nvidia",m) for m in manifest.get("nvidia_free_prototype",[])}
    # The first 4 audited legacy entries predate this manifest.
    legacy={("nous","stepfun/step-5-preview:free"),
      ("nous","poolside/laguna-s-2.1:free"),
      ("nous","meituan/longcat-2.5-preview:free"),
      ("nvidia","nvidia/nemotron-3.5-lightning-30b-a3b")}
    if any((x.get("provider"),x.get("model")) not in valid|legacy for x in entries):
        raise ValueError("unrecognized model in configured fallback: no automatic edit")
    ordered=adaptive_order(entries,catalog=catalog,health=health,usage=usage)
    if ordered==entries:return config_text,ordered
    return replace_fallback_yaml(config_text,ordered),ordered

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--config",type=Path,default=Path.home()/".hermes"/"config.yaml")
    parser.add_argument("--auth",type=Path,default=Path.home()/".hermes"/"auth.json")
    parser.add_argument("--state",type=Path,default=Path.home()/".hermes"/"state.db")
    parser.add_argument("--health",type=Path,default=Path.home()/".local"/"state"/"atlas"/"model-health.sqlite3")
    parser.add_argument("--manifest",type=Path,required=True)
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    manifest=json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("schema_version")!=1:raise ValueError("invalid manifest")
    config=args.config.read_text(encoding="utf-8")
    health=AdaptiveModelHealth(args.health)
    try:
        catalogs=read_catalogs(args.auth)
    except (OSError,ValueError,KeyError,TimeoutError) as ex:
        print("CATALOG_UNAVAILABLE",type(ex).__name__,"no changes made")
        return 2
    usage=read_hermes_usage(args.state)
    new,ordered=plan(config,manifest,catalogs,health,usage)
    print("ADAPTIVE_FALLBACK",{"candidates":len(ordered),
      "catalog_nous":len(catalogs[0]),"catalog_nvidia":len(catalogs[1]),
      "changed":new!=config,"apply":args.apply})
    if new!=config and args.apply:
        backup=atomic_backup_and_write(args.config,new,expected_original=config)
        print("SAFE_BACKUP",backup.name)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
