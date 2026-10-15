"""Authenticated OpenCode v2 HTTP transport; fail closed on ambiguous delivery."""
import base64
import json
from urllib import request,error

class OpenCodeHTTPTransport:
    def __init__(self, *, base_url, password, directory, opener=None, timeout=15):
        if not base_url.startswith("http://127.0.0.1:") and not base_url.startswith("http://localhost:"):
            raise ValueError("OpenCode transport requires loopback")
        if not password or not directory:
            raise ValueError("credentials and directory required")
        self.base=base_url.rstrip("/")
        self.auth="Basic "+base64.b64encode(("opencode:"+password).encode()).decode()
        self.directory=directory
        self.opener=opener or request.urlopen
        self.timeout=timeout
    def _call(self,path,payload=None):
        body=None if payload is None else json.dumps(payload).encode()
        req=request.Request(self.base+path,data=body,method="GET" if body is None else "POST",
            headers={"Authorization":self.auth,"Content-Type":"application/json"})
        with self.opener(req,timeout=self.timeout) as response:
            raw=response.read(2_000_000)
        return json.loads(raw)
    def __call__(self, *, model, prompt, context, max_tokens):
        # Session creation may fail before a prompt was dispatched.
        try:
            obj=self._call("/api/session",{"title":"Atlas-Inference","agent":"plan",
                "model":{"providerID":"opencode","id":model,"variant":"default"},
                "location":{"directory":self.directory}})
        except error.HTTPError as exc:
            if exc.code in (404,429,503):
                return {"status":"unavailable","dispatched":False}
            raise ConnectionError("OpenCode session creation failed") from exc
        sid=obj.get("data",{}).get("id")
        if not isinstance(sid,str) or not sid:
            raise ConnectionError("OpenCode session outcome unknown")
        # Once a session exists, no retry is safe without reconciliation.
        try:
            self._call("/api/session/"+sid+"/prompt",{"text":prompt+"\n"+context})
            state=self._call("/api/session/"+sid).get("data",{})
            if state.get("outcome")!="succeeded":
                raise TimeoutError("OpenCode session pending or unsuccessful")
            messages=self._call("/api/session/"+sid+"/message").get("data",[])
            text="\n".join(p.get("text","") for m in messages if m.get("type")=="assistant"
                for p in m.get("content",[]) if p.get("type")=="text").strip()
            return {"status":"ok","text":text} if text else {"status":"unknown"}
        except Exception as exc:
            raise TimeoutError("OpenCode dispatch outcome uncertain") from exc
