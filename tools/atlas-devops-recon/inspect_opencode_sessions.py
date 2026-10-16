"""Read-only examination of existing OpenCode sessions; no retry or send."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from atlas_agents_api import client
api=client()
for role in ("architecture","security","qa"):
    record=json.loads((ROOT/"opencode-review"/role/"status.json").read_text())
    sid=record["attempts"][0]["session_id"]
    try:
        session=api("/api/session/"+sid).get("data",{})
        messages=api("/api/session/"+sid+"/message").get("data",[])
        print(json.dumps({
         "role":role,"session_id":sid,
         "session_time":session.get("time"),"cost":session.get("cost"),
         "message_metadata":[{"type":m.get("type"),"keys":sorted(m.keys()),
               "role":m.get("role"),"status":m.get("status"),
               "message_id":m.get("id"),"has_error":bool(m.get("error")),
               "content_types":[p.get("type") for p in m.get("content",[]) if isinstance(p,dict)] if isinstance(m.get("content"),list) else None}
               for m in messages[-8:]],
         "assistant_preview":[str(p.get("text",""))[:650] for m in messages
                if isinstance(m,dict) and m.get("type")=="assistant"
                for p in m.get("content",[]) if isinstance(p,dict) and p.get("type")=="text"][-2:]
         },ensure_ascii=False),flush=True)
    except Exception as e:print(json.dumps({"role":role,"error":str(e)[:120]}),flush=True)
