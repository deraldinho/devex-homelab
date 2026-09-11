from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

try:
    import fcntl
except ImportError:
    fcntl=None

_WINDOWS_LOCK=threading.Lock()


def _now(): return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ChatEnvelope:
    message_id: str
    stimulus_id: str
    client_message_id: str
    message: str
    created_at: str
    claimed_at: str | None = None
    acked_at: str | None = None
    attempts: int = 0
    channel: str = "dashboard"
    actor_id: str | None = None
    conversation_id: str | None = None
    reply_target: str | None = None


class ChatInbox:
    def __init__(self,path:Path,*,max_items:int=32,max_message_chars:int=512,max_attempts:int=3):
        if max_items<=0 or max_message_chars<=0 or max_attempts<=0: raise ValueError("bounds must be > 0")
        self.path=Path(path);self.max_items=int(max_items);self.max_message_chars=int(max_message_chars);self.max_attempts=int(max_attempts)
        self.lock_path=self.path.with_name(self.path.name+".lock")

    @contextmanager
    def _lock(self):
        self.lock_path.parent.mkdir(parents=True,exist_ok=True)
        if fcntl is None:
            with _WINDOWS_LOCK: yield
            return
        with self.lock_path.open("a+b") as handle:
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(handle.fileno(),fcntl.LOCK_UN)

    def _load(self):
        if not self.path.is_file(): return []
        try: payload=json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError) as exc: raise ValueError("invalid chat inbox") from exc
        if not isinstance(payload,dict) or payload.get("schema_version")!=1 or not isinstance(payload.get("messages"),list): raise ValueError("invalid chat inbox schema")
        return [ChatEnvelope(**item) for item in payload["messages"]]

    def _write(self,items):
        self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_name(self.path.name+".tmp")
        payload={"schema_version":1,"messages":[asdict(item) for item in items]}
        try:
            with tmp.open("w",encoding="utf-8",newline="\n") as h:
                json.dump(payload,h,ensure_ascii=False,sort_keys=True,separators=(",",":"));h.write("\n");h.flush();os.fsync(h.fileno())
            os.replace(tmp,self.path)
        finally: tmp.unlink(missing_ok=True)

    def enqueue(self,message:str,client_message_id:str,*,channel:str="dashboard",actor_id:str|None=None,conversation_id:str|None=None,reply_target:str|None=None)->ChatEnvelope:
        text=str(message).strip();client=str(client_message_id).strip();channel_name=str(channel).strip().lower()
        if not text: raise ValueError("message is required")
        if len(text)>self.max_message_chars: raise ValueError("message exceeds max_message_chars")
        if not client or len(client)>128: raise ValueError("invalid client_message_id")
        if not channel_name or len(channel_name)>32 or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_.-" for ch in channel_name):
            raise ValueError("invalid channel")
        def route(value):
            if value is None: return None
            normalized=str(value).strip()
            if not normalized or len(normalized)>128: raise ValueError("invalid route metadata")
            return normalized
        actor=route(actor_id);conversation=route(conversation_id);target=route(reply_target)
        with self._lock():
            items=self._load()
            existing=next((x for x in items if x.client_message_id==client),None)
            if existing is not None: return existing
            while len(items)>=self.max_items:
                index=next((i for i,x in enumerate(items) if x.acked_at is not None),None)
                if index is None: raise OverflowError("chat inbox full")
                del items[index]
            mid=str(uuid4());env=ChatEnvelope(
                mid,f"human-chat-{mid}",client,text,_now(),channel=channel_name,
                actor_id=actor,conversation_id=conversation,reply_target=target,
            )
            items.append(env);self._write(items);return env

    def claim_next(self)->ChatEnvelope|None:
        with self._lock():
            items=self._load()
            index=next((i for i,x in enumerate(items) if x.acked_at is None and x.attempts<self.max_attempts),None)
            if index is None:return None
            claimed=replace(items[index],claimed_at=_now(),attempts=items[index].attempts+1)
            items[index]=claimed;self._write(items);return claimed

    def ack(self,message_id:str)->ChatEnvelope:
        with self._lock():
            items=self._load();index=next((i for i,x in enumerate(items) if x.message_id==message_id),None)
            if index is None: raise KeyError(message_id)
            if items[index].acked_at is None: items[index]=replace(items[index],acked_at=_now())
            self._write(items);return items[index]

    def pending_count(self)->int:
        with self._lock(): return sum(1 for x in self._load() if x.acked_at is None)

    def list_items(self)->tuple[ChatEnvelope,...]:
        with self._lock(): return tuple(self._load())
