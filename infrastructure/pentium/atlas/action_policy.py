from __future__ import annotations

from dataclasses import replace

from .action_plan import ActionStatus, ActionType, PlanoAcaoAtlas, transition_action


class ActionPolicy:
    def __init__(self, capability_policy):
        self._capability_policy = capability_policy

    def authorize(self, plan: PlanoAcaoAtlas, *, voice_enabled: bool = False) -> PlanoAcaoAtlas:
        actions=[]; requires_confirmation=False; blocked=False
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
                actions.append(transition_action(action, ActionStatus.AUTHORIZED, reason=decision.razao)); continue
            actions.append(transition_action(action, ActionStatus.AUTHORIZED))
        return replace(plan, actions=tuple(actions), requires_confirmation=requires_confirmation,
                       policy_decision="authorized_with_blocks" if blocked else "authorized")
