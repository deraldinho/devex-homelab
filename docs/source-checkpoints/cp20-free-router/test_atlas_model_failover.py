"""Deterministic tests for free-only model failover with no real provider calls."""
import json
import tempfile
import unittest
from pathlib import Path

from atlas_model_failover import FreeModelFailover, classify_failure, FREE_MODELS

DIRECTORY=Path(__file__).resolve().parent

class FakeClock:
    def __init__(self): self.now=1000
    def time(self): return self.now
    def sleep(self,seconds): self.now+=seconds

class SimulatedAPI:
    def __init__(self,outcomes):
        self.outcomes=list(outcomes)
        self.models=[]
        self.sessions={}
        self.counter=0
    def __call__(self,path,body=None):
        if path=="/api/session":
            self.counter+=1
            sid="session-"+str(self.counter)
            model=body["model"]["id"]
            self.models.append(model)
            scenario=self.outcomes[self.counter-1]
            self.sessions[sid]=scenario
            return {"data":{"id":sid,"location":body["location"]}}
        sid=path.split("/")[3]
        scenario=self.sessions[sid]
        if path.endswith("/prompt"):
            return {"ok":True}
        if path.endswith("/message"):
            return {"data":scenario.get("messages",[])}
        return {"data":{"outcome":scenario.get("outcome","failed"),
                        "cost":scenario.get("cost",0)}}

def rate_limited():
    return {"outcome":"failed","messages":[{"type":"assistant",
        "error":{"status":429,"message":"Rate limit exceeded"}}]}

def success(text="A"*90,cost=0):
    return {"outcome":"succeeded","cost":cost,
        "messages":[{"type":"assistant","content":[{"type":"text","text":text}]}]}

def unavailable():
    return {"outcome":"failed","messages":[{"type":"assistant",
        "error":{"status":503,"message":"Overloaded"}}]}

class FailoverTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.clock=FakeClock()
        self.path=Path(self.temp.name)/"cooldowns.json"
    def runner(self,api,**kwargs):
        return FreeModelFailover(api,state_path=self.path,models=FREE_MODELS[:3],
            clock=self.clock.time,sleep=self.clock.sleep,**kwargs)
    def go(self,runner):
        return runner.run(directory=str(DIRECTORY),title="Test-Agent",prompt="Inspect read-only")
    def test_ranker_order_used_for_first_attempt(self):
        api=SimulatedAPI([success()])
        preferred=FREE_MODELS[1]
        runner=self.runner(api,model_ranker=lambda models:(preferred,FREE_MODELS[0]))
        out=self.go(runner)
        self.assertEqual(out['status'],'succeeded')
        self.assertEqual(api.models,[preferred])
    def test_ranker_cannot_inject_paid_model(self):
        api=SimulatedAPI([success()])
        runner=self.runner(api,model_ranker=lambda models:('paid/unauthorized',))
        with self.assertRaises(ValueError): self.go(runner)
        self.assertEqual(api.models,[])
    def test_ranker_can_skip_all_models(self):
        api=SimulatedAPI([success()])
        runner=self.runner(api,model_ranker=lambda models:())
        self.assertEqual(self.go(runner)['status'],'blocked')
        self.assertEqual(api.models,[])
    def test_429_switches_to_another_free_model(self):
        api=SimulatedAPI([rate_limited(),success()])
        out=self.go(self.runner(api))
        self.assertEqual("succeeded",out["status"])
        self.assertEqual(FREE_MODELS[1],out["model"])
        self.assertEqual(list(FREE_MODELS[:2]),api.models)
        self.assertEqual(["quota","succeeded"],[x["result"] for x in out["attempts"]])
    def test_503_fails_over(self):
        api=SimulatedAPI([unavailable(),success()])
        self.assertEqual("succeeded",self.go(self.runner(api))["status"])
    def test_session_creation_429_is_safe_to_switch(self):
        class CreationRateLimit(SimulatedAPI):
            def __init__(self):
                super().__init__([success()])
                self.first=True
            def __call__(self,path,body=None):
                if path=="/api/session" and self.first:
                    self.first=False
                    raise RuntimeError("API HTTP 429")
                return super().__call__(path,body)
        api=CreationRateLimit()
        out=self.go(self.runner(api))
        self.assertEqual("succeeded",out["status"])
        self.assertEqual([FREE_MODELS[1]],api.models)
        self.assertEqual("quota",out["attempts"][0]["result"])
    def test_cooldown_persists_across_independent_agent_roles(self):
        api=SimulatedAPI([rate_limited(),success(),success()])
        first=self.go(self.runner(api))
        second=self.go(self.runner(api))
        self.assertEqual("succeeded",first["status"])
        self.assertEqual("succeeded",second["status"])
        self.assertEqual([FREE_MODELS[0],FREE_MODELS[1],FREE_MODELS[1]],api.models)
        self.assertEqual("cooldown",second["attempts"][0]["result"])
    def test_401_does_not_switch_provider(self):
        api=SimulatedAPI([{"outcome":"failed","messages":[{"type":"assistant",
            "error":{"status":401,"message":"Credential invalid"}}]}])
        out=self.go(self.runner(api))
        self.assertEqual("blocked",out["status"])
        self.assertEqual(1,len(api.models))
        self.assertEqual("non_retryable",out["attempts"][0]["result"])
    def test_success_nonzero_cost_halts_chain(self):
        api=SimulatedAPI([success(cost=0.01)])
        out=self.go(self.runner(api))
        self.assertEqual("blocked",out["status"])
        self.assertEqual("cost_not_zero",out["attempts"][0]["result"])
        self.assertEqual(1,len(api.models))
    def test_unfinished_request_never_replayed(self):
        api=SimulatedAPI([{"outcome":"running"}])
        out=self.go(self.runner(api,poll_seconds=1,timeout_seconds=2))
        self.assertEqual("blocked",out["status"])
        self.assertEqual("inflight_or_timeout",out["attempts"][0]["result"])
        self.assertEqual(1,len(api.models))
    def test_inflight_session_is_resumed_not_reissued(self):
        task={"outcome":"running","cost":0,"messages":[]}
        api=SimulatedAPI([task])
        first=self.go(self.runner(api,poll_seconds=1,timeout_seconds=2))
        self.assertEqual("inflight_or_timeout",first["attempts"][0]["result"])
        self.assertEqual(1,len(api.models))
        task.update(success("Execution completed successfully without duplicate model request."))
        second=self.go(self.runner(api,poll_seconds=1,timeout_seconds=2))
        self.assertEqual("succeeded",second["status"])
        self.assertTrue(second["attempts"][0]["resumed"])
        self.assertEqual(1,len(api.models))
        self.assertEqual(0,second["cost"])

    def test_zero_models_exhausted_bounded(self):
        api=SimulatedAPI([rate_limited(),rate_limited(),rate_limited()])
        out=self.go(self.runner(api))
        self.assertEqual("blocked",out["status"])
        self.assertEqual(3,len(api.models))
    def test_unknown_paid_model_rejected_before_api(self):
        api=SimulatedAPI([])
        with self.assertRaises(ValueError):
            FreeModelFailover(api,state_path=self.path,models=("gpt-5.5",))
        self.assertEqual([],api.models)
    def test_only_read_only_plan_sessions_are_replayable(self):
        api=SimulatedAPI([])
        runner=self.runner(api)
        with self.assertRaises(ValueError):
            runner.run(directory=str(DIRECTORY),title="editing",
                prompt="change code",agent="build")
        self.assertEqual([],api.models)
    def test_session_location_mismatch_blocks(self):
        class BadLocation(SimulatedAPI):
            def __call__(self,path,body=None):
                ret=super().__call__(path,body)
                if path=="/api/session":
                    ret["data"]["location"]["directory"]="C:/unexpected"
                return ret
        api=BadLocation([rate_limited()])
        out=self.go(self.runner(api))
        self.assertEqual("project_mismatch",out["attempts"][0]["result"])
        self.assertEqual(1,len(api.models))
    def test_error_classification(self):
        self.assertEqual("quota",classify_failure({},
            [{"error":{"status":429,"message":"quota"}}]))
        self.assertEqual("unavailable",classify_failure({},
            [{"error":{"status":503,"message":"unavailable"}}]))
        self.assertEqual("non_retryable",classify_failure({},
            [{"error":{"status":403,"message":"unauthorized"}}]))

if __name__=="__main__":unittest.main()
