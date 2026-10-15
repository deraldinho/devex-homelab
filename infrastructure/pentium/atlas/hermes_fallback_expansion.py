"""Safely extend the Hermes fallback chain without modifying other config keys."""
from __future__ import annotations
import os
import re
from pathlib import Path

def extend_fallbacks(existing, new_nous, new_nvidia):
    if not isinstance(existing,list) or any(not isinstance(x,dict) for x in existing):
        raise ValueError("invalid original fallback chain")
    seen=set()
    for x in existing:
        provider,model=x.get("provider"),x.get("model")
        if not (isinstance(provider,str) and provider and isinstance(model,str) and model):
            raise ValueError("invalid fallback entry")
        key=(provider,model)
        if key in seen:raise ValueError("duplicate existing fallback")
        seen.add(key)
    def new_entries(provider, names):
        result=[]
        for model in names:
            if not isinstance(model,str) or not re.fullmatch(r"[a-zA-Z0-9_./:+-]{3,150}",model):
                raise ValueError("unsafe model id")
            if provider=="nous" and not model.endswith(":free"):
                raise ValueError("Nous additions must be marked free")
            if (provider,model) not in seen:
                seen.add((provider,model))
                data={"provider":provider,"model":model}
                if provider=="nvidia":data["base_url"]="https://integrate.api.nvidia.com/v1"
                result.append(data)
        return result
    nous=new_entries("nous",new_nous)
    nvidia=new_entries("nvidia",new_nvidia)
    position=next((i for i,item in enumerate(existing) if item["provider"]=="nvidia"),len(existing))
    merged=existing[:position]+nous+existing[position:]+nvidia
    if len(merged)>35:raise ValueError("fallback chain limit exceeded")
    return merged

def replace_fallback_yaml(original, entries):
    """Only replace the top-level fallback_providers stanza. Preserve everything else."""
    import yaml
    if not isinstance(original,str):raise TypeError("YAML must be text")
    parsed=yaml.safe_load(original)
    if not isinstance(parsed,dict):raise ValueError("expected YAML mapping")
    if parsed.get("model",{}).get("provider")!="nous":
        raise ValueError("unexpected primary provider; refusing to write")
    lines=original.splitlines(keepends=True)
    starts=[i for i,line in enumerate(lines) if re.match(r"^fallback_providers\s*:\s*(?:#.*)?$",line.rstrip("\r\n"))]
    if len(starts)!=1:raise ValueError("expected exactly one fallback_providers block")
    start=starts[0]
    end=start+1
    while end<len(lines):
        line=lines[end]
        if line.strip() and not line.lstrip().startswith("#") and len(line)==len(line.lstrip()) and not line.startswith("-"):
            break
        end+=1
    block=yaml.safe_dump({"fallback_providers":entries},allow_unicode=True,sort_keys=False)
    transformed="".join(lines[:start])+block+"".join(lines[end:])
    reloaded=yaml.safe_load(transformed)
    if reloaded.get("fallback_providers")!=entries:raise ValueError("fallback roundtrip mismatch")
    for key in parsed:
        if key!="fallback_providers" and reloaded.get(key)!=parsed[key]:
            raise ValueError("unrelated Hermes settings changed")
    return transformed

def atomic_backup_and_write(filename, new_text):
    """Back up full original locally with mode 0600; never emit backup content."""
    import datetime
    path=Path(filename)
    if not path.is_file() or path.is_symlink():raise ValueError("configuration is not a regular file")
    original=path.read_bytes()
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backups=path.parent/"backups"
    backups.mkdir(mode=0o700,parents=True,exist_ok=True)
    target=backups/("atlas-fallback-before-"+stamp+".yaml")
    fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"wb") as output:
        output.write(original);output.flush();os.fsync(output.fileno())
    temp=path.with_name(path.name+".atlas-new")
    fd=os.open(temp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        with os.fdopen(fd,"wb") as output:
            output.write(new_text.encode("utf-8"));output.flush();os.fsync(output.fileno())
        os.replace(temp,path)
    finally:
        if temp.exists():temp.unlink()
    return target
