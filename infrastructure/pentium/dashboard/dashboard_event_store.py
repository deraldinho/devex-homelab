from __future__ import annotations

import json
import os
from pathlib import Path

class DashboardEventStore:
    def __init__(self,path:Path,*,max_events:int=128,max_bytes:int=262144):
        if max_events<=0 or max_bytes<=0: raise ValueError('bounds must be > 0')
        self.path=Path(path); self.max_events=int(max_events); self.max_bytes=int(max_bytes)

    def _load(self):
        if not self.path.is_file(): return []
        events=[]
        for line in self.path.read_text(encoding='utf-8').splitlines():
            try: item=json.loads(line)
            except json.JSONDecodeError: continue
            if isinstance(item,dict) and isinstance(item.get('id'),int): events.append(item)
        return events

    def _write(self,events):
        self.path.parent.mkdir(parents=True,exist_ok=True); tmp=self.path.with_name(self.path.name+'.tmp')
        while events:
            text=''.join(json.dumps(e,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n' for e in events[-self.max_events:])
            if len(text.encode('utf-8'))<=self.max_bytes: break
            events=events[1:]
        try:
            with tmp.open('w',encoding='utf-8',newline='\n') as h:
                h.write(text if events else ''); h.flush(); os.fsync(h.fileno())
            os.replace(tmp,self.path)
        finally: tmp.unlink(missing_ok=True)

    def append(self,event_type:str,payload:dict):
        events=self._load(); next_id=(events[-1]['id']+1) if events else 1
        event={'id':next_id,'type':str(event_type)[:64],'payload':dict(payload)}
        events.append(event); self._write(events[-self.max_events:]); return event

    def after(self,last_event_id:int|None):
        threshold=int(last_event_id or 0)
        return [e for e in self._load() if int(e.get('id',0))>threshold][-self.max_events:]
