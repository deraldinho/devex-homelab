"""Explicit opt-in deployment of audited free Hermes fallback models.

Never reads credentials, prints configuration, or modifies the primary model.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .hermes_fallback_expansion import (
    extend_fallbacks,replace_fallback_yaml,atomic_backup_and_write)

def plan(config, manifest):
    import yaml
    data=yaml.safe_load(config)
    if not isinstance(manifest,dict) or manifest.get("schema_version")!=1:
        raise ValueError("invalid manifest")
    additions=manifest.get("nous_free"),manifest.get("nvidia_free_prototype")
    if any(not isinstance(x,list) for x in additions):
        raise ValueError("missing curated model lists")
    existing=data.get("fallback_providers",[])
    extended=extend_fallbacks(existing,*additions)
    transformed=replace_fallback_yaml(config,extended)
    return transformed,extended

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--manifest",type=Path,required=True)
    parser.add_argument("--config",type=Path,default=Path.home()/".hermes"/"config.yaml")
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    cfg=args.config.read_text(encoding="utf-8")
    manifest=json.loads(args.manifest.read_text(encoding="utf-8"))
    rendered,chain=plan(cfg,manifest)
    print("FALLBACK_CHECK",{"total":len(chain),"nous":sum(x["provider"]=="nous" for x in chain),
          "nvidia":sum(x["provider"]=="nvidia" for x in chain),
          "changed":rendered!=cfg,"apply":args.apply})
    if args.apply and rendered!=cfg:
        # Everything including any unrelated secrets remains on the same host.
        backup=atomic_backup_and_write(args.config,rendered)
        print("LOCAL_BACKUP_CREATED",backup.name)
    elif args.apply:
        print("NO_CHANGE_ALREADY_CONFIGURED")
if __name__=="__main__":main()
