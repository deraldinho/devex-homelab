import json
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from infrastructure.pentium.atlas.action_plan import (
    ActionStatus, ActionType, AtlasAction, PlanoAcaoAtlas, transition_action,
)
from infrastructure.pentium.atlas.action_plan_store import ActionPlanStore


def terminal_plan(index: int, *, sensitive: bool = False):
    params = {"capability": "get_host_status", "arguments": {"host": "x99"}}
    if sensitive:
        params["arguments"]["secret"] = "do-not-persist"
    action = AtlasAction.create(ActionType.CAPABILITY_REQUEST, target="x99", parameters=params)
    action = transition_action(action, ActionStatus.AUTHORIZED)
    action = transition_action(action, ActionStatus.EXECUTING)
    action = transition_action(action, ActionStatus.COMPLETED)
    return PlanoAcaoAtlas.create(
        stimulus_id=f"s-{index}", objective=f"plano {index}", confidence=.8,
        response_text="resultado", actions=[action],
    )


class ActionPlanStoreTests(unittest.TestCase):
    def test_current_roundtrip_preserves_plan_identity(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); store = ActionPlanStore(root/"current.json", root/"history.jsonl")
            plan = terminal_plan(1)
            store.save_current(plan)
            loaded = store.load_current()
        self.assertEqual(plan.plan_id, loaded.plan_id)
        self.assertEqual(plan.actions[0].status, loaded.actions[0].status)

    def test_history_is_bounded_and_sanitizes_sensitive_parameters(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); history = root/"history.jsonl"
            store = ActionPlanStore(root/"current.json", history, max_history=8, max_bytes=65536)
            for i in range(12): store.append_terminal(terminal_plan(i, sensitive=True))
            lines = history.read_text(encoding="utf-8").splitlines()
            payload = history.read_text(encoding="utf-8").lower()
        self.assertLessEqual(len(lines), 8)
        self.assertNotIn("do-not-persist", payload)
        self.assertNotIn('"secret"', payload)
        self.assertTrue(all(json.loads(line)["schema_version"] == 1 for line in lines))

    def test_nonterminal_plan_is_rejected_from_terminal_history(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp); store=ActionPlanStore(root/"current.json",root/"history.jsonl")
            plan=PlanoAcaoAtlas.create(stimulus_id="s",objective="x",confidence=.5,response_text=None,actions=[AtlasAction.create(ActionType.WAIT,parameters={"duration_ms":10})])
            with self.assertRaises(ValueError): store.append_terminal(plan)
