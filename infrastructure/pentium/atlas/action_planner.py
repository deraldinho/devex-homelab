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

    def _locomotion_actions(self,response,entity_id,trigger_kind):
        actions=[]
        name=getattr(response,"intencao",None)
        params=dict(getattr(response,"parametros_intencao",None) or {})

        # 1. Intenções explícitas de movimento/pet
        if name in {"mover_para","navegar","navigate_to","ir_para"}:
            target=params.get("target") or params.get("alvo") or entity_id or "center"
            mode=params.get("mode") or "hop"
            actions.append(AtlasAction.create(ActionType.NAVIGATE_TO,target=str(target),
                parameters={"target":str(target),"mode":str(mode)}))
        elif name in {"acao_pet","comportamento_pet","pet_action"}:
            act=params.get("action") or params.get("acao") or "PATROL"
            dur=int(params.get("duration_ms") or 6000)
            actions.append(AtlasAction.create(ActionType.SET_PET_ACTION,
                parameters={"action":str(act).upper(),"duration_ms":dur}))

        # 2. Orquestração contextual
        motivo=str(getattr(response,"motivo","") or "")
        text=str(getattr(response,"texto","") or "").lower()
        has_nav=any(a.type is ActionType.NAVIGATE_TO for a in actions)
        has_pet=any(a.type is ActionType.SET_PET_ACTION for a in actions)

        if not has_pet:
            if any(w in text for w in ("sente","descans","repous","sit")):
                actions.append(AtlasAction.create(ActionType.SET_PET_ACTION,
                    parameters={"action":"SIT","duration_ms":8000}))
            elif any(w in text for w in ("carinho","fofa","parabens","obrigad","poke")):
                actions.append(AtlasAction.create(ActionType.SET_PET_ACTION,
                    parameters={"action":"POKE","duration_ms":1200}))
            elif motivo=="recuperacao_importante":
                actions.append(AtlasAction.create(ActionType.SET_PET_ACTION,
                    parameters={"action":"SIT","duration_ms":6000}))

        if not has_nav:
            if trigger_kind=="chat" or motivo=="interacao_humana":
                actions.append(AtlasAction.create(ActionType.NAVIGATE_TO,target="chat",
                    parameters={"target":"chat","mode":"hop"}))
            elif entity_id in {"services","core"}:
                actions.append(AtlasAction.create(ActionType.NAVIGATE_TO,target="services",
                    parameters={"target":"services","mode":"hop"}))
            elif entity_id=="mind":
                actions.append(AtlasAction.create(ActionType.NAVIGATE_TO,target="mind",
                    parameters={"target":"mind","mode":"hop"}))

        return actions

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
        locomotion=self._locomotion_actions(response,entity_id,trigger_kind)
        actions.extend(locomotion)
        if not actions:
            actions.append(AtlasAction.create(ActionType.WAIT,parameters={"duration_ms":250}))
        objective=(getattr(response,"resumo",None) or text or "processar estimulo")
        confidence=getattr(response,"confianca",None)
        return PlanoAcaoAtlas.create(stimulus_id=str(stimulus_id),objective=str(objective),
            confidence=0.0 if confidence is None else float(confidence),response_text=text,actions=actions,trigger_kind=trigger_kind)
