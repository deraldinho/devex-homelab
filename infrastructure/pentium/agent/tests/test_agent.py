import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import Agent, UnknownActionError


class AgentContractTests(unittest.TestCase):
    def test_registry_exposes_only_x99_status(self):
        calls = []

        def handler():
            calls.append("called")
            return {"status": "healthy"}

        agent = Agent(x99_status_handler=handler)
        self.assertEqual(agent.available_actions(), ("x99.status",))
        self.assertEqual(calls, [])

    def test_unknown_action_is_rejected_before_handler(self):
        calls = []

        def handler():
            calls.append("called")
            return {"status": "healthy"}

        agent = Agent(x99_status_handler=handler)
        with self.assertRaises(UnknownActionError):
            agent.execute("x99.shell")
        self.assertEqual(calls, [])
