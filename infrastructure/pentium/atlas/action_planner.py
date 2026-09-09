from __future__ import annotations

from .action_plan import ActionType, AtlasAction, PlanoAcaoAtlas
from .capability_registry import atlas_capability_registry

_EXPR_BY_REASON={
    "mudanca_estado":"CURIOSO",
    "interacao_humana":"ENGAJADO",
    "criticidade":"ATENTO",
    "recuperacao_importante":"RECUPERANDO",
}


class ActionPlanner:
    def __init__(self, registry=None):
        self._registry=registry or atlas_capability_registry()

    def _capability_action(self,response,entity_id):
        name=getattr(response,"intencao",None)
        params=dict(getattr(response,"parametros_intencao",None) or {})
        if not name:
            return None
        try:
            spec=self._registry.obter(name)
        except KeyError:
            return None
        if not spec.validar_parametros(params):
            return None
        return AtlasAction.create(ActionType.CAPABILITY_REQUEST,target=entity_id,
            parameters={"capability":name,"arguments":params})

    def plan(self,stimulus_id,entity_id,response,*,trigger_kind="observation")->PlanoAcaoAtlas:
        actions=[]
        text=getattr(response,"texto",None)
        if text:
            actions.append(AtlasAction.create(ActionType.CHAT_REPLY))
        if entity_id:
            actions.append(AtlasAction.create(ActionType.LOOK_AT,target=str(entity_id),parameters={"direction":"target"}))
        motivo=getattr(response,"motivo",None)
        expression=_EXPR_BY_REASON.get(str(motivo))
        if expression:
            actions.append(AtlasAction.create(ActionType.SET_EXPRESSION,parameters={"expression":expression}))
        if str(motivo)=="interacao_humana":
            actions.append(AtlasAction.create(ActionType.SET_GESTURE,parameters={"gesture":"ABERTO","arm":"right"}))
        if bool(getattr(response,"solicitar_fala",False)):
            actions.append(AtlasAction.create(ActionType.SPEAK_TTS))
        capability=self._capability_action(response,entity_id)
        if capability is not None:
            actions.append(capability)
        if not actions:
            actions.append(AtlasAction.create(ActionType.WAIT,parameters={"duration_ms":250}))
        objective=(getattr(response,"resumo",None) or text or "processar estimulo")
        confidence=getattr(response,"confianca",None)
        return PlanoAcaoAtlas.create(stimulus_id=str(stimulus_id),objective=str(objective),
            confidence=0.0 if confidence is None else float(confidence),response_text=text,actions=actions,trigger_kind=trigger_kind)
