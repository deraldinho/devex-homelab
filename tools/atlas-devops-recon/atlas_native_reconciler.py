"""Fail-closed reconciliation for a previously claimed, externally executed task.

No session replay, network calls, or implicit trust of receipt fields.
The caller must independently authenticate the provider receipt and attest
session ownership before invoking reconciliation.
"""
from atlas_native_executor import status, finish
from atlas_native_session_registry import session_for_task

def reconcile_terminal(db, task_id, *, receipt, verifier):
    current = status(db, task_id)
    if current is None:
        raise KeyError("unclaimed task")
    if current["status"] != "IN_FLIGHT":
        return {"status": current["status"], "reconciled": False}
    if not callable(verifier):
        raise TypeError("trusted receipt verifier required")
    if not isinstance(receipt, dict) or receipt.get("task_id") != task_id:
        raise ValueError("task identity mismatch")
    binding = session_for_task(db, task_id)
    if (binding is None or receipt.get("session_id") != binding["session_id"]
            or receipt.get("issuer") != binding["issuer"]):
        return {"status": "IN_FLIGHT", "reconciled": False}
    if not verifier(receipt):
        return {"status": "IN_FLIGHT", "reconciled": False}
    if receipt.get("outcome") not in ("succeeded", "failed", "cancelled"):
        return {"status": "IN_FLIGHT", "reconciled": False}
    if receipt.get("cost") != 0 or type(receipt.get("cost")) not in (int, float):
        return {"status": "IN_FLIGHT", "reconciled": False}
    outcome = "SUCCEEDED" if receipt["outcome"] == "succeeded" else "FAILED"
    result = {"status":outcome, "source":"verified_external_receipt",
              "session_id":receipt.get("session_id"), "cost":0,
              "task_id":task_id}
    if not isinstance(result["session_id"],str) or not result["session_id"]:
        return {"status":"IN_FLIGHT","reconciled":False}
    return {**finish(db,task_id,result), "reconciled":True}
