"""Non-mutating audit of OpenCode review sessions and coordinator contracts."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from atlas_agents_api import client
api=client()
report=[]
for role in ("architecture","security","qa"):
    target=ROOT/"opencode-review"/role
    record=json.loads((target/"status.json").read_text())
    pending=json.loads((target/"model-state.json").read_text()).get("pending",{})
    session_id=record["attempts"][0]["session_id"]
    data=api("/api/session/"+session_id).get("data",{})
    messages=api("/api/session/"+session_id+"/message").get("data",[])
    events=[]
    for msg in messages:
        if msg.get("type")=="assistant":
            events.append({"finish":msg.get("finish"),"cost":msg.get("cost"),
                           "tools":[{"name":part.get("name") or part.get("tool"),
                                     "status":part.get("status")} for part in msg.get("content",[]) if part.get("type")=="tool"]})
    item={"role":role,"session_id":session_id,"outcome":data.get("outcome"),
          "cost":data.get("cost"),"pending":any(p.get("session_id")==session_id for p in pending.values()),
          "assistant_messages":len(events),"tool_calls":sum(len(e["tools"]) for e in events),
          "terminal_finish":events[-1]["finish"] if events else None,
          "finish_types":sorted(set(str(e["finish"]) for e in events)),
          "tool_names":sorted(set(str(tool["name"]) for e in events for tool in e["tools"]))}
    report.append(item)
path=ROOT/"OPENCODE-ORCHESTRATION-AUDIT.json"
path.write_text(json.dumps({"sessions":report,"coordinator_issue":"outcome field missing; generic status never certified"},indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False),flush=True)
