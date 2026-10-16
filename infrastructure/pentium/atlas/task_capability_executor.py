from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .self_work import SelfWorkRuntime, SelfWorkState


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskCapabilityExecutor:
    def __init__(self, runtime: SelfWorkRuntime, *, specialist_gateway=None,
                 specialist_candidate_provider=None):
        self.runtime = runtime
        self.specialist_gateway = specialist_gateway
        # Injected trusted metadata source only. Never load candidates from
        # capability params or infer a global / on-disk Hermes catalog.
        self.specialist_candidate_provider = specialist_candidate_provider

    def __call__(self, capability: str, params: Optional[Dict[str, Any]] = None, plan: Any = None, action: Any = None) -> Dict[str, Any]:
        params = params or {}
        now = _utc_now()

        if capability == "task_specialist_review":
            if self.specialist_gateway is None:
                return {"status": "ERROR", "error": "agency_disabled"}
            if self.runtime.current is None:
                return {"status": "ERROR", "error": "no_active_task"}
            from .agency_specialists import AgencyRequest
            requested_specialist = str(params.get("specialist") or "")
            selected = (requested_specialist,)

            # Explicit opt-in only. A trusted source provides bounded candidate
            # metadata; this selector never grants capability permissions.
            if requested_specialist == "auto":
                current = self.runtime.current
                if current.state != SelfWorkState.WORKING:
                    return {"status": "ERROR", "error": "agency_task_not_working"}
                config = getattr(self.specialist_gateway, "config", None)
                if getattr(config, "enabled", None) is not True:
                    return {"status": "ERROR", "error": "agency_disabled"}
                project = params.get("project")
                objective = params.get("objective")
                if not isinstance(project, str) or not isinstance(objective, str):
                    return {"status": "ERROR", "error": "agency_invalid_request"}
                try:
                    # Apply the canonical request size/type constraints before
                    # consulting even a trusted external metadata provider.
                    AgencyRequest(
                        task_id=current.item_id, project=project,
                        objective=objective, specialists=(),
                    )
                    expiry = datetime.fromisoformat(current.valid_until)
                    if expiry.tzinfo is None or datetime.now(timezone.utc) > expiry:
                        return {"status": "ERROR", "error": "agency_task_expired"}
                except (ValueError, TypeError):
                    return {"status": "ERROR", "error": "agency_invalid_request"}
                if project not in getattr(config, "projects", ()):
                    return {"status": "ERROR", "error": "agency_project_not_allowlisted"}
                budget = getattr(config, "max_agents", None)
                if type(budget) is not int or not 1 <= budget <= 2:
                    return {"status": "ERROR", "error": "agency_disabled"}
                if not callable(self.specialist_candidate_provider):
                    return {"status": "ERROR", "error": "agency_selection_unavailable"}
                try:
                    from .agency_specialist_selector import select_specialists
                    candidates = self.specialist_candidate_provider(project, objective)
                    selected = select_specialists(
                        project, objective, candidates, max_agents=budget,
                    )
                except Exception:
                    # No provider errors or untrusted candidate content in results.
                    return {"status": "ERROR", "error": "agency_selection_invalid"}
                if not selected:
                    return {"status": "ERROR", "error": "agency_no_specialists"}

            try:
                request = AgencyRequest(
                    task_id=self.runtime.current.item_id,
                    project=str(params.get("project") or ""),
                    objective=str(params.get("objective") or ""),
                    specialists=selected,
                )
            except ValueError:
                return {"status": "ERROR", "error": "agency_invalid_request"}
            report = self.specialist_gateway.execute(request)
            return {
                "status": report.status, "reason": report.reason,
                "summary": report.summary, "agent_slugs": list(report.agent_slugs),
                "evidence_refs": list(report.evidence_refs),
                "proposed_changes": list(report.proposed_changes),
                "tests_run": list(report.tests_run),
                "limitations": list(report.limitations),
            }

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
