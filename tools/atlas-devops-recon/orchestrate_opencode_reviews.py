"""Bounded independent OpenCode review agents; zero-cost, plan-only.

Runs against checkpoint staging; NEVER integrates agent patches automatically.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from atlas_agents_api import client
from atlas_model_failover import FreeModelFailover

TASKS={
 "architecture": "Review native workflow/dispatch/executor/session registry in this directory. Identify highest risk correctness and crash-recovery gaps with file and function references. Suggest tests; do not modify files.",
 "security": "Review native session registry, reconciler, receipt authentication and free runner. Specifically identify trust, session creation-to-binding gap and replay risks, with cited code and concrete regression tests. Read only, no edits.",
 "qa": "Independently examine native modules and tests. Identify untested edge cases and inconsistent contracts with specific functions and minimal test designs. Do not modify files."
}
def run(role, task):
    target=ROOT/"opencode-review"/role
    target.mkdir(parents=True,exist_ok=True)
    manager=FreeModelFailover(client(),state_path=target/"model-state.json",
        models=("mimo-v2.6-flash-free","ling-3.1-flash-free",
                "nemotron-3.5-lightning-free"),timeout_seconds=70,
        max_attempts=3,poll_seconds=3)
    prompt=("You are an independent read-only software auditor. Restrict activity to this source tree, "
            "do not edit files, run commands, read credentials or access external services. "
            "Return findings with severity and concrete file/symbol evidence; do not claim to have run tests. "
            +task)
    try:
        outcome=manager.run(directory=str(ROOT),title="AtlasNativeReview-"+role,
                            prompt=prompt,agent="plan")
        slim={k:v for k,v in outcome.items() if k!="text"}
        (target/"status.json").write_text(json.dumps(slim,ensure_ascii=False,indent=2),encoding="utf-8")
        if outcome.get("text"):
            (target/"review.md").write_text(outcome["text"],encoding="utf-8")
        return {"role":role,"status":outcome.get("status"),"model":outcome.get("model"),
                "cost":outcome.get("cost"),"attempts":outcome.get("attempts")}
    except Exception as error:
        report={"role":role,"status":"blocked","error_type":type(error).__name__}
        (target/"status.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        return report

if __name__=="__main__":
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(run,r,p):r for r,p in TASKS.items()}
        for future in as_completed(futures):
            print(json.dumps(future.result(),ensure_ascii=False),flush=True)
