from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .self_work import SelfWorkRuntime, SelfWorkState


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskCapabilityExecutor:
    def __init__(self, runtime: SelfWorkRuntime, *, delegation_bridge=None):
        self.runtime = runtime
        self.delegation_bridge = delegation_bridge
        self._source_origin = None

    def set_source_origin(self, envelope):
        """Only the trusted inbox envelope can bind a return destination."""
        self._source_origin = None
        if envelope is not None and getattr(envelope, "channel", None) == "discord":
            self._source_origin = {
                "channel": "discord",
                "actor_id": getattr(envelope, "actor_id", None),
                "reply_target": getattr(envelope, "reply_target", None),
                "client_message_id": getattr(envelope, "client_message_id", None),
            }

    def __call__(self, capability: str, params: Optional[Dict[str, Any]] = None, plan: Any = None, action: Any = None) -> Dict[str, Any]:
        params = params or {}
        now = _utc_now()

        if capability == "task_status":
            current = self.runtime.current
            if current is None:
                answer = {
                    "has_active_task": False,
                    "status": "IDLE",
                    "summary": "Nenhuma tarefa autônoma em andamento no momento.",
                }
                if self.delegation_bridge is not None:
                    latest = self.delegation_bridge.latest_result()
                    if latest:
                        answer["delegation"] = latest
                return answer
            answer = {
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
            if self.delegation_bridge is not None:
                latest = self.delegation_bridge.read_result(current.item_id)
                if latest:
                    answer["delegation"] = latest
            return answer

        elif capability == "task_create":
            objective = str(params.get("objective", "")).strip()
            area = str(params.get("area", "general")).strip()
            if not objective:
                return {"status": "ERROR", "error": "objective_required"}
            try:
                item = self.runtime.propose(objective, area, now=now)
                # Persist the external proposal BEFORE activating local work.
                # A failed write must never be represented as CREATED or WORKING.
                if self.delegation_bridge is not None:
                    try:
                        self.delegation_bridge.propose(item, source_origin=self._source_origin)
                    except Exception as error:
                        # The write may have succeeded before the exception.
                        # Invalidate the proposal if the bridge is reachable.
                        try:
                            blocker = getattr(self.delegation_bridge, "block_proposal", None)
                            if blocker is not None:
                                blocker(item.item_id, reason="external_write_uncertain")
                        except Exception:
                            pass  # Never claim that reconciliation is complete.
                        return {
                            "status": "DELEGATION_BLOCKED",
                            "item_id": item.item_id,
                            "objective": item.objective,
                            "area": item.area,
                            "state": "CANDIDATE",
                            "delegation": {"state": "blocked", "reason": type(error).__name__},
                            "summary": "Proposta externa nao confirmada; exige reconciliacao manual.",
                        }
                try:
                    self.runtime.activate(now=now)
                    self.runtime.begin_work(now=now)
                except Exception as error:
                    if self.delegation_bridge is not None:
                        try:
                            self.delegation_bridge.block_proposal(
                                item.item_id, reason="local_transition_failed")
                        except Exception:
                            return {"status": "RECONCILIATION_REQUIRED",
                                    "item_id": item.item_id, "reason": "invalidation_failed"}
                        return {"status": "DELEGATION_BLOCKED",
                                "item_id": item.item_id, "reason": type(error).__name__}
                    raise
                answer = {
                    "status": "CREATED",
                    "item_id": item.item_id,
                    "objective": item.objective,
                    "area": item.area,
                    "state": self.runtime.current.state.value if self.runtime.current else "UNKNOWN",
                    "summary": f"Tarefa criada e iniciada com sucesso: '{item.objective}' (ID: {item.item_id}).",
                }
                if self.delegation_bridge is not None:
                    answer["delegation"] = {"state": "awaiting_approval", "task_id": item.item_id}
                return answer
            except Exception as exc:
                return {"status": "ERROR", "error": str(exc)}

        elif capability == "task_complete":
            reason = str(params.get("reason", "concluida_pelo_operador")).strip()
            current = self.runtime.current
            if current is None:
                return {"status": "ERROR", "error": "no_active_task_to_complete"}
            try:
                if self.delegation_bridge is not None:
                    # A local task cannot claim completion before the authorized
                    # external worker has returned a terminal success.
                    verified_reader = getattr(self.delegation_bridge, "read_verified_result", None)
                    external = verified_reader(current.item_id) if verified_reader is not None else None
                    if not isinstance(external, dict) or external.get("state") != "completed" or not external.get("session_id"):
                        return {"status": "DELEGATION_BLOCKED",
                                "item_id": current.item_id,
                                "reason": "external_completion_unverified"}
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
                if self.delegation_bridge is not None:
                    # Do not leave an externally approvable proposal after
                    # local cancellation, even when it was never executed.
                    try:
                        self.delegation_bridge.block_proposal(
                            current.item_id, reason="local_abandoned")
                    except Exception:
                        return {"status": "RECONCILIATION_REQUIRED",
                                "item_id": current.item_id,
                                "reason": "external_invalidation_failed"}
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
