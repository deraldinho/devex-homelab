import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from infrastructure.pentium.agent.agent import Agent
from infrastructure.pentium.agent.cli import load_config, main


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

    def test_schema_v2_requires_explicit_managed_host_contract(self):
        payload = {
            "schema_version": 2,
            "managed_hosts": [{
                "host_id": "x99",
                "enrollment": "MANAGED",
                "user": "deral",
                "host": "192.168.88.20",
                "identity_file": "~/.ssh/id_ed25519_x99",
                "known_hosts_file": "~/.ssh/known_hosts",
                "platform": "windows",
                "allowed_reads": ["uptime", "memory"],
                "connect_timeout_seconds": 5,
                "max_output_bytes": 65536,
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = load_config(path)
        self.assertEqual(loaded["schema_version"], 2)
        self.assertEqual(loaded["managed_hosts"][0]["known_hosts_file"], "~/.ssh/known_hosts")


if __name__ == "__main__":
    unittest.main()
