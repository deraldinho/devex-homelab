import json
import unittest
from types import SimpleNamespace

from infrastructure.pentium.atlas.action_plan import ActionType
from infrastructure.pentium.atlas.action_planner import ActionPlanner


def response(**overrides):
    values = dict(
        texto="Estou verificando.", resumo="mudanca", confianca=.8,
        motivo="mudanca_estado", intencao=None, parametros_intencao=None,
        requer_confirmacao=False, solicitar_fala=False,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


class ActionPlannerTests(unittest.TestCase):
    def test_text_and_entity_generate_chat_and_look_actions(self):
        plan = ActionPlanner().plan("s1", "x99", response())
        self.assertEqual(ActionType.CHAT_REPLY, plan.actions[0].type)
        self.assertIn(ActionType.LOOK_AT, [a.type for a in plan.actions])
        self.assertIn(ActionType.SET_EXPRESSION, [a.type for a in plan.actions])

    def test_valid_capability_is_structured_and_unknown_shell_is_ignored(self):
        planner = ActionPlanner()
        valid = planner.plan("s1", "x99", response(
            intencao="get_host_status", parametros_intencao={"host":"x99"}))
        cap = next(a for a in valid.actions if a.type is ActionType.CAPABILITY_REQUEST)
        self.assertEqual("get_host_status", cap.parameters["capability"])
        unsafe = planner.plan("s2", "x99", response(
            intencao="shell", parametros_intencao={"command":"rm -rf /"}))
        serialized = json.dumps(unsafe.to_dict()).lower()
        self.assertNotIn("shell", serialized)
        self.assertNotIn("rm -rf", serialized)

    def test_speak_request_is_explicit_action(self):
        plan = ActionPlanner().plan("s1", "x99", response(solicitar_fala=True))
        self.assertIn(ActionType.SPEAK_TTS, [a.type for a in plan.actions])


class ActionPlannerContinuousIntentTests(unittest.TestCase):
    def test_silent_tracking_keeps_visual_actions_and_suppresses_communication_and_capability(self):
        plan = ActionPlanner().plan(
            "s1", "core",
            response(
                texto="mensagem repetida", solicitar_fala=True,
                intencao="get_host_status", parametros_intencao={"host":"core"},
            ),
            communication_mode="silent_tracking",
        )
        types=[action.type for action in plan.actions]
        self.assertIn(ActionType.LOOK_AT, types)
        self.assertIn(ActionType.SET_EXPRESSION, types)
        self.assertNotIn(ActionType.CHAT_REPLY, types)
        self.assertNotIn(ActionType.SPEAK_TTS, types)
        self.assertNotIn(ActionType.CAPABILITY_REQUEST, types)
