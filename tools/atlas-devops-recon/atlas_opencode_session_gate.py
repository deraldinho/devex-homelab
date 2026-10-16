"""Conservative evaluation of API v2 OpenCode sessions (no side effects)."""
READ_ONLY_TOOLS=frozenset(("glob","grep","read"))
def evaluate(session,messages):
    if not isinstance(session,dict) or not isinstance(messages,list):
        return {"status":"BLOCKED","reason":"INVALID_API_RESPONSE"}
    assistant=[m for m in messages if isinstance(m,dict) and m.get("type")=="assistant"]
    tools=[]
    for msg in assistant:
        for part in msg.get("content",()):
            if isinstance(part,dict) and part.get("type")=="tool":
                tools.append(part.get("name") or part.get("tool"))
    unsafe=sorted({str(name) for name in tools if name not in READ_ONLY_TOOLS})
    if unsafe:
        return {"status":"BLOCKED","reason":"UNAUTHORIZED_TOOL_USED","tools":unsafe}
    if not assistant or assistant[-1].get("finish") not in ("stop","end_turn"):
        return {"status":"PENDING","reason":"NO_TERMINAL_ASSISTANT"}
    if not isinstance(session.get("cost"),(int,float)) or type(session["cost"]) is bool or session["cost"]!=0:
        return {"status":"BLOCKED","reason":"UNVERIFIED_FREE_COST"}
    text_parts=[part.get("text","") for part in assistant[-1].get("content",())
                if isinstance(part,dict) and part.get("type")=="text"]
    if len("".join(text_parts).strip())<60:
        return {"status":"BLOCKED","reason":"EMPTY_REVIEW"}
    return {"status":"REVIEW_CANDIDATE","reason":"REQUIRES_INDEPENDENT_VALIDATION"}
