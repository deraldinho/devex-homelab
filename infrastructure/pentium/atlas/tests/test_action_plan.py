import unittest

from infrastructure.pentium.atlas.action_plan import (
    ActionStatus, ActionType, AtlasAction, PlanoAcaoAtlas, transition_action,
)


class ActionPlanTests(unittest.TestCase):
    def test_create_plan_starts_actions_planned_and_allows_legal_transition(self):
        action = AtlasAction.create(ActionType.CHAT_REPLY)
        plan = PlanoAcaoAtlas.create(
            stimulus_id="s1", objective="responder", confidence=.8,
            response_text="oi", actions=[action],
        )
        self.assertEqual(ActionStatus.PLANNED, plan.actions[0].status)
        authorized = transition_action(plan.actions[0], ActionStatus.AUTHORIZED)
        self.assertEqual(ActionStatus.AUTHORIZED, authorized.status)

    def test_illegal_transition_is_rejected(self):
        action = AtlasAction.create(ActionType.CHAT_REPLY)
        with self.assertRaises(ValueError):
            transition_action(action, ActionStatus.COMPLETED)

    def test_action_parameters_are_allowlisted_by_type(self):
        look = AtlasAction.create(ActionType.LOOK_AT, target="x99", parameters={"direction": "right"})
        self.assertEqual("right", look.parameters["direction"])
        with self.assertRaises(ValueError):
            AtlasAction.create(ActionType.LOOK_AT, target="x99", parameters={"shell": "rm -rf /"})
