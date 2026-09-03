import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import Agent
from cli import main


class AgentCliTests(unittest.TestCase):
    def test_known_action_emits_json_and_healthy_exit(self):
        agent = Agent(x99_status_handler=lambda: {"status": "healthy", "hostname": "x99"})
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["x99.status"], agent=agent)
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue())["hostname"], "x99")

    def test_unknown_action_returns_contract_error(self):
        agent = Agent(x99_status_handler=lambda: {"status": "healthy"})
        error = io.StringIO()
        with redirect_stderr(error):
            exit_code = main(["x99.shell"], agent=agent)
        self.assertEqual(exit_code, 2)
        self.assertIn("unknown action", error.getvalue())
