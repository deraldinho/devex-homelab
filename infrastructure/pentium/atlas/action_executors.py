from __future__ import annotations

from dataclasses import replace

from .action_plan import ActionStatus, ActionType, PlanoAcaoAtlas, transition_action


class ActionExecutorRegistry:
    def __init__(self, visual_getter=None, visual_writer=None, *, chat_sink=None, tts_sink=None, capability_sink=None, event_sink=None):
        self._visual_getter=visual_getter; self._visual_writer=visual_writer
        self._chat_sink=chat_sink; self._tts_sink=tts_sink; self._capability_sink=capability_sink
        self._event_sink=event_sink

    def _visual(self, action):
        if self._visual_getter is None or self._visual_writer is None:
            raise RuntimeError("visual executor unavailable")
        state=self._visual_getter(); p=dict(action.parameters)
        if action.type is ActionType.LOOK_AT:
            state=replace(state,foco_visual=action.target or "neutro",direcao_olhar=str(p.get("direction") or "centro"),modo="OBSERVANDO")
        elif action.type is ActionType.SET_EXPRESSION:
            state=replace(state,expressao=str(p.get("expression") or state.expressao),intensidade_expressao=float(p.get("intensity",state.intensidade_expressao)))
        elif action.type is ActionType.SET_GESTURE:
            state=replace(state,gesto_atual=str(p.get("gesture") or "NENHUM"),lado_gesto=str(p.get("arm") or "none"))
        elif action.type is ActionType.SET_POSTURE:
            state=replace(state,postura_atual=str(p.get("posture") or "NEUTRO"))
        elif action.type is ActionType.NAVIGATE_TO:
            target=str(p.get("target") or action.target or "auto")
            state=replace(state,alvo_locomocao=target,foco_visual=target)
        elif action.type is ActionType.SET_PET_ACTION:
            state=replace(state,acao_pet=str(p.get("action") or "PATROL"))
        self._visual_writer(state)
        if self._event_sink is not None:
            try:
                self._event_sink("visual_action", {
                    "action_type": action.type.value,
                    "target": getattr(state, "alvo_locomocao", "auto"),
                    "action": getattr(state, "acao_pet", "PATROL"),
                    "expression": str(getattr(state, "expressao", "SERENO")),
                    "focus": getattr(state, "foco_visual", "neutro"),
                    "duration_ms": int(p.get("duration_ms") or 6000),
                    "parameters": p,
                })
            except Exception:
                pass

    def _execute_one(self, plan, action):
        if action.type in {ActionType.LOOK_AT,ActionType.SET_EXPRESSION,ActionType.SET_GESTURE,ActionType.SET_POSTURE,ActionType.NAVIGATE_TO,ActionType.SET_PET_ACTION}:
            self._visual(action)
        elif action.type is ActionType.CHAT_REPLY:
            if self._chat_sink is not None: self._chat_sink(plan.response_text or "", plan, action)
        elif action.type is ActionType.SPEAK_TTS:
            if self._tts_sink is None: raise RuntimeError("tts executor unavailable")
            self._tts_sink(plan.response_text or "", plan, action)
        elif action.type is ActionType.CAPABILITY_REQUEST:
            if self._capability_sink is None: raise RuntimeError("capability executor unavailable")
            self._capability_sink(str(action.parameters["capability"]),dict(action.parameters.get("arguments") or {}),plan,action)
        elif action.type is ActionType.WAIT:
            return

    def execute(self, plan: PlanoAcaoAtlas) -> PlanoAcaoAtlas:
        output=[]
        for action in plan.actions:
            if action.status is not ActionStatus.AUTHORIZED or action.reason == "confirmation_required":
                output.append(action); continue
            running=transition_action(action,ActionStatus.EXECUTING)
            try:
                self._execute_one(plan,running)
                output.append(transition_action(running,ActionStatus.COMPLETED))
            except Exception as exc:
                output.append(transition_action(running,ActionStatus.FAILED,reason=type(exc).__name__))
        return replace(plan,actions=tuple(output))
