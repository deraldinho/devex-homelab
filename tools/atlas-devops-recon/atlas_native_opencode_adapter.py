"""Native orchestration -> existing free-model runner boundary.

Runner is injected and must be sandboxed. This adapter intentionally does not
instantiate a network client; production attestation and credentials are separate.
"""
from atlas_native_executor import claim, finish

def process_review(db, task_id, runner):
    if not callable(runner):
        raise TypeError("runner must be callable")
    lease = claim(db, task_id)
    if not lease["claimed"]:
        return {"status":lease["status"], "dispatched":False}
    task = lease["payload"]
    if (task.get("read_only") is not True
            or task.get("execution_authorized") is not False):
        return {"status":"IN_FLIGHT","dispatched":False}
    try:
        response = runner(task)
    except Exception:
        # Unknown provider state: no retries until an authenticated reconciler
        # proves termination and absence of irreversible side effects.
        return {"status":"IN_FLIGHT","dispatched":True}
    if not isinstance(response,dict):
        return {"status":"IN_FLIGHT","dispatched":True}
    if response.get("status") not in ("succeeded","failed"):
        return {"status":"IN_FLIGHT","dispatched":True}
    cost = response.get("cost")
    if type(cost) not in (int,float) or cost != 0:
        return {"status":"IN_FLIGHT","dispatched":True}
    # Success is only review evidence; no action or deployment approval.
    result = {"status":"SUCCEEDED" if response["status"]=="succeeded" else "FAILED",
              "cost":0, "role":task["role"], "read_only":True,
              "review_text":str(response.get("text") or "")[:12000]}
    return {**finish(db,task_id,result), "dispatched":True}
