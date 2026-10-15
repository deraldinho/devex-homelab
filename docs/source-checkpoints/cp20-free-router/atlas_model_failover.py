"""Free-only, bounded failover for READ-ONLY OpenCode agent sessions.

Never replay a session whose outcome is unknown or still running.
Never use models outside the explicit zero-price allowlist.
"""
from __future__ import annotations
import hashlib
import json
import os
import time
from pathlib import Path

FREE_MODELS = (
    "ling-3.1-flash-free",
    "mimo-v2.6-flash-free",
    "nemotron-3.5-lightning-free",
    "step-5-preview-free",
    "exo-free",
)
_RETRYABLE_CODES = {404, 408, 409, 425, 429, 500, 502, 503, 504}
_COOLDOWN = {"quota": 600, "unavailable": 120, "missing": 1800}

class FailoverUnavailable(RuntimeError):
    pass

def classify_failure(state: dict, messages: list) -> str:
    """Only well-understood provider failures qualify for replay."""
    errors = []
    if isinstance(state.get("error"), dict):
        errors.append(state["error"])
    for message in messages:
        if isinstance(message, dict) and isinstance(message.get("error"), dict):
            errors.append(message["error"])
    for item in errors:
        status = item.get("status")
        try:
            status = int(status)
        except (ValueError, TypeError):
            status = None
        obj = str(item.get("message") or "").lower()
        # A specific non-retryable HTTP status beats ambiguous prose.
        if status in (400, 401, 402, 403, 405, 422):
            return "non_retryable"
        if status == 429 or any(k in obj for k in ("rate limit", "quota exceeded", "too many requests")):
            return "quota"
        if status == 404 or "model not found" in obj:
            return "missing"
        if status in _RETRYABLE_CODES or any(k in obj for k in (
            "overloaded", "temporarily unavailable", "connection refused", "service unavailable"
        )):
            return "unavailable"
    return "non_retryable"

def _response_text(messages: list) -> str:
    return "\n".join(
        str(part.get("text", ""))
        for msg in messages if isinstance(msg, dict) and msg.get("type") == "assistant"
        for part in msg.get("content", ()) if isinstance(part, dict) and part.get("type") == "text"
    ).strip()

class FreeModelFailover:
    def __init__(self, api, *, state_path: Path, models=FREE_MODELS,
                 clock=time.time, sleep=time.sleep, poll_seconds=3,
                 timeout_seconds=90, max_attempts=5, model_ranker=None):
        if not models or any(m not in FREE_MODELS for m in models):
            raise ValueError("Only preapproved free models are permitted")
        if len(set(models)) != len(models):
            raise ValueError("Duplicate fallback models forbidden")
        self.api=api
        self.path=Path(state_path)
        self.models=tuple(models)
        self.model_ranker=model_ranker
        self.clock=clock
        self.sleep=sleep
        self.poll_seconds=poll_seconds
        self.timeout_seconds=timeout_seconds
        self.max_attempts=min(max_attempts,len(self.models))
        self._pending={}
        self._cooldowns=self._load_cooldowns()

    def _load_cooldowns(self) -> dict:
        try:
            data=json.loads(self.path.read_text(encoding="utf-8"))
            self._pending={key:entry for key,entry in data.get("pending",{}).items()
                           if isinstance(key,str) and isinstance(entry,dict)
                           and entry.get("model") in FREE_MODELS
                           and isinstance(entry.get("session_id"),str)}
            return {model:float(until) for model,until in data.get("cooldowns",{}).items()
                    if model in FREE_MODELS and float(until)>self.clock()}
        except (OSError,ValueError,TypeError,AttributeError):
            return {}

    def _write_cooldowns(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        data={"version":1,"cooldowns":self._cooldowns,"pending":self._pending}
        tmp=self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data,indent=2),encoding="utf-8")
        os.replace(tmp,self.path)

    def _set_cooldown(self,model,reason):
        self._cooldowns[model]=self.clock()+_COOLDOWN.get(reason,120)
        self._write_cooldowns()

    def run(self, *, directory: str, title: str, prompt: str, agent="plan") -> dict:
        if agent != "plan":
            raise ValueError("Automated replay supports read-only plan agents ONLY")
        location=str(Path(directory).resolve())
        if not Path(location).is_dir():
            raise ValueError("Project directory does not exist")
        attempts=[]
        job_key=hashlib.sha256(
            json.dumps([location,title,prompt],ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        pending=self._pending.get(job_key)
        if pending:
            model=pending["model"]
            sid=pending["session_id"]
            record={"model":model,"session_id":sid,"resumed":True}
            attempts.append(record)
            try:
                start=self.clock()
                state={}
                while self.clock()-start < self.timeout_seconds:
                    state=self.api("/api/session/"+sid).get("data",{})
                    if state.get("outcome") in ("succeeded","failed","cancelled"):
                        break
                    self.sleep(self.poll_seconds)
                outcome=state.get("outcome")
                if outcome not in ("succeeded","failed","cancelled"):
                    record["result"]="inflight_or_timeout"
                    return {"status":"blocked","attempts":attempts}
                messages=self.api("/api/session/"+sid+"/message").get("data",[])
                self._pending.pop(job_key,None)
                self._write_cooldowns()
                if outcome=="succeeded":
                    cost=state.get("cost")
                    answer=_response_text(messages)
                    record["cost"]=cost
                    if cost==0 and len(answer)>=60:
                        record["result"]="succeeded"
                        return {"status":"succeeded","model":model,
                                "text":answer,"cost":cost,"attempts":attempts}
                    record["result"]="cost_not_zero" if cost!=0 else "empty_response"
                    return {"status":"blocked","attempts":attempts}
                if outcome=="cancelled":
                    record["result"]="cancelled"
                    return {"status":"blocked","attempts":attempts}
                reason=classify_failure(state,messages)
                record["result"]=reason
                if reason=="non_retryable":
                    return {"status":"blocked","attempts":attempts}
                self._set_cooldown(model,reason)
            except (OSError,RuntimeError,ValueError,KeyError,TypeError):
                record["result"]="pending_lookup_error"
                return {"status":"blocked","attempts":attempts}
        new_sessions=0
        ordered=self.models
        if self.model_ranker is not None:
            proposed=tuple(self.model_ranker(self.models))
            if len(set(proposed))!=len(proposed) or any(m not in self.models for m in proposed):
                raise ValueError('ranker selected unauthorized or duplicate models')
            ordered=proposed
        for model in ordered:
            if self._cooldowns.get(model,0)>self.clock():
                attempts.append({"model":model,"result":"cooldown"})
                continue
            if new_sessions>=self.max_attempts:
                break
            new_sessions+=1
            record={"model":model}
            attempts.append(record)
            created=None
            try:
                created=self.api("/api/session",{
                    "title":title+"-"+model,
                    "agent":"plan",
                    "model":{"providerID":"opencode","id":model,"variant":"default"},
                    "location":{"directory":location},
                }).get("data",{})
                session_id=created.get("id")
                if not isinstance(session_id,str) or not session_id:
                    record["result"]="invalid_session"
                    break
                record["session_id"]=session_id
                returned=created.get("location",{}).get("directory")
                if not isinstance(returned,str) or Path(returned).resolve()!=Path(location):
                    record["result"]="project_mismatch"
                    break
                # Persist the session ID BEFORE dispatch so even ambiguous network
                # errors cannot cause an unintentional duplicate prompt.
                self._pending[job_key]={"session_id":session_id,"model":model}
                self._write_cooldowns()
                self.api("/api/session/"+session_id+"/prompt",{"text":prompt})
                start=self.clock()
                state={}
                while self.clock()-start < self.timeout_seconds:
                    state=self.api("/api/session/"+session_id).get("data",{})
                    if state.get("outcome") in ("succeeded","failed","cancelled"):
                        break
                    self.sleep(self.poll_seconds)
                outcome=state.get("outcome")
                if outcome not in ("succeeded","failed","cancelled"):
                    # May still be executing: NEVER send same request to a second model.
                    record["result"]="inflight_or_timeout"
                    break
                messages=self.api("/api/session/"+session_id+"/message").get("data",[])
                self._pending.pop(job_key,None)
                self._write_cooldowns()
                if outcome == "succeeded":
                    cost=state.get("cost")
                    record["cost"]=cost
                    if cost != 0:
                        record["result"]="cost_not_zero"
                        break
                    answer=_response_text(messages)
                    if len(answer)<60:
                        record["result"]="empty_response"
                        break
                    record["result"]="succeeded"
                    self._cooldowns.pop(model,None)
                    self._write_cooldowns()
                    return {"status":"succeeded","model":model,"text":answer,
                            "cost":cost,"attempts":attempts}
                if outcome == "cancelled":
                    record["result"]="cancelled"
                    break
                reason=classify_failure(state,messages)
                record["result"]=reason
                if reason=="non_retryable":
                    break
                self._set_cooldown(model,reason)
            except (OSError,RuntimeError,ValueError,KeyError,TypeError) as exc:
                # A failed session-creation request has not dispatched a prompt.
                # Such 429/5xx errors are safe to retry on a different model.
                issue=str(exc)
                if created is None and "API HTTP " in issue:
                    try:
                        status=int(issue.rsplit("API HTTP ",1)[1].split()[0])
                    except (ValueError,IndexError):
                        status=None
                    if status in _RETRYABLE_CODES:
                        reason="quota" if status==429 else "unavailable"
                        record["result"]=reason
                        self._set_cooldown(model,reason)
                        continue
                # Failure after session creation is ambiguous: no replay.
                record["result"]="transport_uncertain"
                record["error_type"]=type(exc).__name__
                break
        return {"status":"blocked","attempts":attempts}
