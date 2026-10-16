from __future__ import annotations

from dataclasses import replace

from .action_plan import ActionStatus, ActionType, PlanoAcaoAtlas, transition_action


class ActionPolicy:
    def __init__(self, capability_policy, *, coherence_gate=None):
        self._capability_policy = capability_policy
        self._coherence_gate = coherence_gate

    def authorize(self, plan: PlanoAcaoAtlas, *, voice_enabled: bool = False,
                  evidence=(), correlation_id: str | None = None,
                  human_approval: bool = False) -> PlanoAcaoAtlas:
        actions=[]; requires_confirmation=False; blocked=False
        correlation = str(correlation_id or plan.plan_id)
        for action in plan.actions:
            if action.status is not ActionStatus.PLANNED:
                actions.append(action); continue
            if action.type is ActionType.SPEAK_TTS and not voice_enabled:
                actions.append(transition_action(action, ActionStatus.BLOCKED, reason="voice_paused")); blocked=True; continue
            if action.type is ActionType.CAPABILITY_REQUEST:
                name=str(action.parameters.get("capability") or "")
                arguments=dict(action.parameters.get("arguments") or {})
                decision=self._capability_policy.avaliar(name, arguments)
                if decision.requer_confirmacao:
                    actions.append(transition_action(action, ActionStatus.AUTHORIZED, reason="confirmation_required")); requires_confirmation=True; continue
                if not decision.autorizada:
                    actions.append(transition_action(action, ActionStatus.BLOCKED, reason=decision.razao)); blocked=True; continue
                if self._coherence_gate is not None:
                    verdict=self._coherence_gate.evaluate(capability=name, level=decision.nivel,
                                                          memories=evidence, correlation_id=correlation,
                                                          human_approval=human_approval)
                    if not verdict.allowed:
                        actions.append(transition_action(action, ActionStatus.BLOCKED,
                                                         reason=f"memory_coherence:{verdict.reason}")); blocked=True; continue
                    if verdict.requires_human_approval and not human_approval:
                        actions.append(transition_action(action, ActionStatus.AUTHORIZED,
                                                         reason=f"memory_coherence:{verdict.reason}")); requires_confirmation=True; continue
                actions.append(transition_action(action, ActionStatus.AUTHORIZED, reason=decision.razao)); continue
            actions.append(transition_action(action, ActionStatus.AUTHORIZED))
        return replace(plan, actions=tuple(actions), requires_confirmation=requires_confirmation,
                       policy_decision="authorized_with_blocks" if blocked else "authorized")
