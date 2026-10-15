"""Authenticated OpenCode v2 HTTP transport; fail closed on ambiguous delivery."""
import base64
import json
import hashlib
from .opencode_session_ledger import SessionLedger
from urllib import request,error,parse

class OpenCodeHTTPTransport:
    def __init__(self, *, base_url, password, directory, opener=None, timeout=15, journal_path=None):
        target=parse.urlsplit(base_url)
        if target.scheme!="http" or target.hostname not in ("127.0.0.1","localhost") or not target.port or target.username or target.password or target.path not in ("","/") or target.query or target.fragment:
            raise ValueError("OpenCode transport requires strict loopback URL")
        if not password or not directory:
            raise ValueError("credentials and directory required")
        self.base=base_url.rstrip("/")
        self.auth="Basic "+base64.b64encode(("opencode:"+password).encode()).decode()
        self.directory=directory
        self.opener=opener or request.urlopen
        self.timeout=timeout
        self.ledger=SessionLedger(journal_path) if journal_path is not None else None
    def _call(self,path,payload=None):
        body=None if payload is None else json.dumps(payload).encode()
        req=request.Request(self.base+path,data=body,method="GET" if body is None else "POST",
            headers={"Authorization":self.auth,"Content-Type":"application/json"})
        with self.opener(req,timeout=self.timeout) as response:
            raw=response.read(2_000_000)
        return json.loads(raw)
    def __call__(self, *, model, prompt, context, max_tokens):
        if self.ledger is None:
            return self._execute(model=model,prompt=prompt,context=context,max_tokens=max_tokens)
        lock=self.ledger.acquire()
        try:
            return self._execute(model=model,prompt=prompt,context=context,max_tokens=max_tokens)
        finally:
            self.ledger.release(lock)
    def _execute(self, *, model, prompt, context, max_tokens):
        job=hashlib.sha256(json.dumps([model,prompt,context,max_tokens],sort_keys=True).encode()).hexdigest()
        title='Atlas-Inference-'+job[:24]
        prior=self.ledger.read() if self.ledger else None
        if prior:
            if prior.get('job')!=job:
                raise TimeoutError('another OpenCode job is unresolved')
            if prior['state']=='completed':
                return {'status':'ok','text':prior['text']}
            if not prior.get('session_id'):
                recovered=self.find_created_session(prior,model,title)
                if recovered is None:
                    raise TimeoutError('session creation uncertain; no unique verified match')
                self.ledger.save({'job':job,'title':title,'model':model,'state':'dispatch_uncertain','session_id':recovered})
                return self.reconcile(recovered,job)
            return self.reconcile(prior['session_id'],job)
        if self.ledger:self.ledger.save({'job':job,'state':'creating','title':title,'model':model})
        # Session creation may fail before a prompt was dispatched.
        try:
            obj=self._call("/api/session",{"title":title,"agent":"plan",
                "model":{"providerID":"opencode","id":model,"variant":"default"},
                "location":{"directory":self.directory}})
        except error.HTTPError as exc:
            if exc.code in (404,429,503):
                return {"status":"unavailable","dispatched":False}
            raise ConnectionError("OpenCode session creation failed") from exc
        sid=obj.get("data",{}).get("id")
        if not isinstance(sid,str) or not sid:
            raise ConnectionError("OpenCode session outcome unknown")
        if self.ledger:self.ledger.save({'job':job,'state':'created','session_id':sid})
        # Once a session exists, no retry is safe without reconciliation.
        try:
            if self.ledger:self.ledger.save({'job':job,'state':'dispatch_uncertain','session_id':sid})
            self._call("/api/session/"+sid+"/prompt",{"text":prompt+"\n"+context})
            state=self._call("/api/session/"+sid).get("data",{})
            if state.get("outcome")!="succeeded":
                raise TimeoutError("OpenCode session pending or unsuccessful")
            messages=self._call("/api/session/"+sid+"/message").get("data",[])
            text="\n".join(p.get("text","") for m in messages if m.get("type")=="assistant"
                for p in m.get("content",[]) if p.get("type")=="text").strip()
            if text and self.ledger:
                self.ledger.save({'job':job,'state':'completed','session_id':sid,'text':text})
            return {"status":"ok","text":text} if text else {"status":"unknown"}
        except Exception as exc:
            raise TimeoutError("OpenCode dispatch outcome uncertain") from exc
    def reconcile(self,sid,job):
        """Read only. Never resend a prompt to an existing session."""
        try:
            state=self._call("/api/session/"+sid).get("data",{})
            if state.get("outcome")!="succeeded":
                raise TimeoutError("OpenCode session not reconciled")
            messages=self._call("/api/session/"+sid+"/message").get("data",[])
            text="\n".join(p.get("text","") for m in messages if m.get("type")=="assistant"
                for p in m.get("content",[]) if p.get("type")=="text").strip()
            if not text:raise TimeoutError("missing completed response")
            if self.ledger:self.ledger.save({"job":job,"session_id":sid,"state":"completed","text":text})
            return {"status":"ok","text":text}
        except Exception as exc:
            raise TimeoutError("OpenCode reconciliation inconclusive") from exc
    def find_created_session(self,record,model,title):
        """Read-only recovery for a uniquely identifiable created session."""
        if record.get("state")!="creating" or record.get("title")!=title or record.get("model")!=model:
            return None
        try:
            sessions=self._call("/api/session").get("data",[])
        except Exception:
            return None
        if not isinstance(sessions,list):
            return None
        matches=[item for item in sessions if isinstance(item,dict)
            and item.get("title")==title and item.get("agent")=="plan"
            and isinstance(item.get("model"),dict)
            and item["model"].get("providerID")=="opencode"
            and item["model"].get("id")==model
            and isinstance(item.get("location"),dict)
            and item["location"].get("directory")==self.directory
            and isinstance(item.get("id"),str) and item.get("id")]
        return matches[0]["id"] if len(matches)==1 else None
