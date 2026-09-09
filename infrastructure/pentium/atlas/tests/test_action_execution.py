import unittest
from dataclasses import replace

from infrastructure.pentium.atlas.action_plan import ActionStatus, ActionType, AtlasAction, PlanoAcaoAtlas
from infrastructure.pentium.atlas.action_policy import ActionPolicy
from infrastructure.pentium.atlas.action_executors import ActionExecutorRegistry
from infrastructure.pentium.atlas.capability_registry import atlas_capability_registry
from infrastructure.pentium.atlas.policy_capabilities import PolicyCapabilities
from infrastructure.pentium.atlas.modelo_visual_atlas import EstadoVisualAtlas


def visual():
    return EstadoVisualAtlas("OCIOSO","SERENO",.25,"neutro","centro","NENHUM",.25,.25,False,False,False,False,400)


def action_of(plan, kind): return next(a for a in plan.actions if a.type is kind)


class ActionExecutionTests(unittest.TestCase):
    def test_tts_is_blocked_and_visual_action_executes(self):
        plan=PlanoAcaoAtlas.create(stimulus_id="s1",objective="responder",confidence=.8,response_text="oi",actions=[
            AtlasAction.create(ActionType.LOOK_AT,target="x99",parameters={"direction":"centro"}),
            AtlasAction.create(ActionType.SPEAK_TTS),
        ])
        caps=PolicyCapabilities(atlas_capability_registry(),read_auto_allow=("get_host_status",),control_allow=())
        authorized=ActionPolicy(caps).authorize(plan,voice_enabled=False)
        self.assertEqual(ActionStatus.BLOCKED,action_of(authorized,ActionType.SPEAK_TTS).status)
        self.assertEqual("voice_paused",action_of(authorized,ActionType.SPEAK_TTS).reason)
        state=[visual()]
        executed=ActionExecutorRegistry(lambda:state[0],lambda v:state.__setitem__(0,v)).execute(authorized)
        self.assertEqual("x99",state[0].foco_visual)
        self.assertEqual(ActionStatus.COMPLETED,action_of(executed,ActionType.LOOK_AT).status)

    def test_capability_read_is_authorized_but_unknown_never_executes(self):
        plan=PlanoAcaoAtlas.create(stimulus_id="s",objective="check",confidence=.7,response_text=None,actions=[
            AtlasAction.create(ActionType.CAPABILITY_REQUEST,target="x99",parameters={"capability":"get_host_status","arguments":{"host":"x99"}})
        ])
        caps=PolicyCapabilities(atlas_capability_registry(),read_auto_allow=("get_host_status",),control_allow=())
        out=ActionPolicy(caps).authorize(plan,voice_enabled=False)
        self.assertEqual(ActionStatus.AUTHORIZED,out.actions[0].status)
