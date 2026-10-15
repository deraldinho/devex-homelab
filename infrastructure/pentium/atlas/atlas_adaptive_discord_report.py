"""Emit deduplicated Atlas model-health reports through the native Discord action queue."""
from __future__ import annotations
import hashlib
import json
import os
import time
from pathlib import Path

def compose(result, *, now, previous=None):
    if not isinstance(result,dict):raise ValueError("invalid result")
    try:
        count=int(result["candidates"]); nous=int(result["catalog_nous"]); nvidia=int(result["catalog_nvidia"])
    except (ValueError,TypeError,KeyError) as exc:
        raise ValueError("invalid model health summary") from exc
    changed=bool(result["changed"])
    signature=hashlib.sha256(f"{count}|{nous}|{nvidia}|{changed}".encode()).hexdigest()
    old=previous or {}
    hourly=now-float(old.get("last_report",0))>=3600
    if signature==old.get("signature") and not hourly:return None,signature
    if changed:
        msg=f"Atlas • fallback alterado: {count} modelos; catálogos Nous {nous}, NVIDIA {nvidia}. Revise o roteamento."
    else:
        msg=f"Atlas • monitoramento: {count} fallbacks; catálogos Nous {nous}, NVIDIA {nvidia}; nenhuma reordenação necessária."
    return msg,signature

def report(result,*,queue_path,state_path,now=None):
    now=float(time.time() if now is None else now)
    queue=Path(queue_path);state=Path(state_path)
    previous=json.loads(state.read_text()) if state.is_file() else {}
    message,signature=compose(result,now=now,previous=previous)
    if message is None:return False
    # Native Atlas gateway reads this same newline-delimited action queue.
    queue.parent.mkdir(parents=True,exist_ok=True)
    action={"id":"atlas-adaptive-"+str(int(now*1000)),"capability":"discord_send_alert",
        "arguments":{"channel":"","message":message},"enqueued_at":now}
    with queue.open("a",encoding="utf-8") as f:
        f.write(json.dumps(action,ensure_ascii=False)+"\n")
        f.flush();os.fsync(f.fileno())
    state.parent.mkdir(parents=True,exist_ok=True)
    tmp=state.with_name(state.name+".tmp")
    tmp.write_text(json.dumps({"signature":signature,"last_report":now}),encoding="utf-8")
    os.replace(tmp,state)
    return True
