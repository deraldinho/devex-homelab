from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clip(value, limit: int = 512):
    if value is None:
        return None
    return str(value)[:limit]


class CognitiveObservablePublisher:
    def __init__(self, state_path: Path, timeline_path: Path, *, max_events: int = 64, max_text_chars: int = 512):
        self.state_path = Path(state_path)
        self.timeline_path = Path(timeline_path)
        self.max_events = max(8, int(max_events))
        self.max_text_chars = max(64, int(max_text_chars))

    def _write_state(self, payload: dict) -> dict:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_name(self.state_path.name + ".tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, self.state_path)
        return payload

    def _append_event(self, event: dict) -> None:
        self.timeline_path.parent.mkdir(parents=True, exist_ok=True)
        events = []
        if self.timeline_path.is_file():
            for line in self.timeline_path.read_text(encoding="utf-8").splitlines()[-(self.max_events - 1):]:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    events.append(item)
        keys=("source_stimulus_id","state","activity","motivo","summary","intention")
        if events and all(events[-1].get(k)==event.get(k) for k in keys):
            return
        events.append(event)
        tmp = self.timeline_path.with_name(self.timeline_path.name + ".tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            for item in events[-self.max_events:]:
                handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, self.timeline_path)

    def publish_phase(self, snapshot, *, state: str, activity: str, task: str | None = None, motivo: str | None = None, detail: str | None = None):
        now = _utc_now()
        payload = {
            "schema_version": 2, "generated_at": now, "source_stimulus_id": snapshot.source_stimulus_id,
            "entity_id": getattr(snapshot, "entity_id", None), "state": state, "activity": activity,
            "task": _clip(task, self.max_text_chars), "motivo": _clip(motivo, self.max_text_chars),
            "detail": _clip(detail, self.max_text_chars), "last_result": None,
        }
        self._write_state(payload)
        self._append_event({"timestamp": now, "source_stimulus_id": snapshot.source_stimulus_id, "state": state, "activity": activity, "motivo": payload["motivo"], "summary": payload["detail"]})
        return payload

    def publish_result(self, snapshot, response, *, task: str | None = None):
        now = _utc_now()
        reason = _clip(getattr(response, "razao", None), self.max_text_chars)
        summary = _clip(getattr(response, "resumo", None), self.max_text_chars)
        preview = _clip(getattr(response, "texto", None), self.max_text_chars)
        intention = _clip(getattr(response, "intencao", None), self.max_text_chars)
        activated = bool(getattr(response, "ativado", False))
        state = "DEGRADADA" if reason else ("AGUARDANDO_CONFIRMACAO" if getattr(response, "requer_confirmacao", False) else "OBSERVANDO")
        result = {
            "activated": activated, "reason": reason, "motivo": _clip(getattr(response, "motivo", None), self.max_text_chars),
            "summary": summary, "response_preview": preview, "intention": intention,
            "confidence": getattr(response, "confianca", None), "backend": _clip(getattr(response, "backend", None), self.max_text_chars),
            "duration_ms": getattr(response, "duracao_ms", None),
            "requires_confirmation": bool(getattr(response, "requer_confirmacao", False)),
            "intention_authorized": bool(getattr(response, "intencao_autorizada", False)),
        }
        payload = {
            "schema_version": 2, "generated_at": now, "source_stimulus_id": snapshot.source_stimulus_id,
            "entity_id": getattr(snapshot, "entity_id", None), "state": state,
            "activity": "resultado_concluido", "task": _clip(task, self.max_text_chars),
            "motivo": result["motivo"], "detail": summary or reason or preview, "last_result": result,
        }
        self._write_state(payload)
        self._append_event({"timestamp": now, "source_stimulus_id": snapshot.source_stimulus_id, "state": state, "activity": "resultado_concluido", "motivo": result["motivo"], "summary": payload["detail"], "intention": intention, "confidence": result["confidence"]})
        return payload

    def publish(self, snapshot, response):
        return self.publish_result(snapshot, response, task="formular_resposta_cognitiva")


class CognitiveActionEventPublisher:
    def __init__(self, path: Path, *, max_events: int = 128, max_bytes: int = 262144):
        self.path=Path(path); self.max_events=max(8,int(max_events)); self.max_bytes=max(4096,int(max_bytes))

    def publish(self, event_type: str, payload: dict) -> dict:
        self.path.parent.mkdir(parents=True,exist_ok=True)
        events=[]
        if self.path.is_file():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try: item=json.loads(line)
                except json.JSONDecodeError: continue
                if isinstance(item,dict): events.append(item)
        next_id=(int(events[-1].get("id",0))+1) if events else 1
        event={"id":next_id,"timestamp":_utc_now(),"type":str(event_type)[:64],"payload":dict(payload)}
        events.append(event); events=events[-self.max_events:]
        while events:
            text="".join(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n" for x in events)
            if len(text.encode("utf-8"))<=self.max_bytes: break
            events.pop(0)
        tmp=self.path.with_name(self.path.name+".tmp")
        try:
            with tmp.open("w",encoding="utf-8",newline="\n") as handle:
                handle.write(text); handle.flush(); os.fsync(handle.fileno())
            os.replace(tmp,self.path)
        finally: tmp.unlink(missing_ok=True)
        return event
