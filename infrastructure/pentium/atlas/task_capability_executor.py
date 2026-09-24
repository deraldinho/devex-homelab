from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .self_work import SelfWorkRuntime, SelfWorkState


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskCapabilityExecutor:
    def __init__(self, runtime: SelfWorkRuntime):
        self.runtime = runtime

    def __call__(self, capability: str, params: Optional[Dict[str, Any]] = None, plan: Any = None, action: Any = None) -> Dict[str, Any]:
        params = params or {}
        now = _utc_now()

        if capability == "task_status":
            current = self.runtime.current
            if current is None:
                return {
                    "has_active_task": False,
                    "status": "IDLE",
                    "summary": "Nenhuma tarefa autônoma em andamento no momento.",
                }
            return {
                "has_active_task": True,
                "status": current.state.value,
                "item_id": current.item_id,
                "objective": current.objective,
                "area": current.area,
                "created_at": current.created_at,
                "valid_until": current.valid_until,
                "operations_used": current.operations_used,
                "inferences_used": current.inferences_used,
                "summary": f"Tarefa ativa [{current.state.value}]: '{current.objective}' na área '{current.area}' (Ops: {current.operations_used}, Infs: {current.inferences_used}).",
            }

        elif capability == "task_create":
            objective = str(params.get("objective", "")).strip()
            area = str(params.get("area", "general")).strip()
            if not objective:
                return {"status": "ERROR", "error": "objective_required"}
            try:
                item = self.runtime.propose(objective, area, now=now)
                self.runtime.activate(now=now)
                self.runtime.begin_work(now=now)
                return {
                    "status": "CREATED",
                    "item_id": item.item_id,
                    "objective": item.objective,
                    "area": item.area,
                    "state": self.runtime.current.state.value if self.runtime.current else "UNKNOWN",
                    "summary": f"Tarefa criada e iniciada com sucesso: '{item.objective}' (ID: {item.item_id}).",
                }
            except Exception as exc:
                return {"status": "ERROR", "error": str(exc)}

        elif capability == "task_complete":
            reason = str(params.get("reason", "concluida_pelo_operador")).strip()
            current = self.runtime.current
            if current is None:
                return {"status": "ERROR", "error": "no_active_task_to_complete"}
            try:
                if current.state != SelfWorkState.REVIEWING:
                    if current.state in {SelfWorkState.ACTIVE, SelfWorkState.PAUSED}:
                        self.runtime.begin_work(now=now)
                    self.runtime.review(now=now)
                done = self.runtime.complete(now=now)
                return {
                    "status": "COMPLETED",
                    "item_id": done.item_id,
                    "objective": done.objective,
                    "reason": reason,
                    "summary": f"Tarefa '{done.objective}' concluída com sucesso.",
                }
            except Exception as exc:
                return {"status": "ERROR", "error": str(exc)}

        elif capability == "task_abandon":
            reason = str(params.get("reason", "cancelada_pelo_operador")).strip()
            current = self.runtime.current
            if current is None:
                return {"status": "ERROR", "error": "no_active_task_to_abandon"}
            try:
                abandoned = self.runtime.abandon(now=now, reason=reason)
                return {
                    "status": "ABANDONED",
                    "item_id": abandoned.item_id,
                    "objective": abandoned.objective,
                    "reason": reason,
                    "summary": f"Tarefa '{abandoned.objective}' cancelada.",
                }
            except Exception as exc:
                return {"status": "ERROR", "error": str(exc)}

        return {"status": "ERROR", "error": f"Capacidade de tarefa desconhecida: {capability}"}
