import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import health


class HealthContractTests(unittest.TestCase):
    def setUp(self):
        self.inventory = {
            "schema_version": 1,
            "nodes": {
                "pentium": {
                    "role": "homelab.control",
                    "tailscale_name": "pentium",
                    "tailscale_ipv4": "100.107.230.78",
                    "ssh_port": 22,
                    "required": True,
                },
                "core": {
                    "role": "homelab.compute",
                    "tailscale_name": "core",
                    "tailscale_ipv4": "100.97.105.116",
                    "ssh_port": 22,
                    "required": True,
                },
            },
        }
    def tailscale_status(self, pentium_online=True, core_online=True):
        return {
            "Self": {
                "HostName": "x99",
                "Online": True,
                "TailscaleIPs": ["100.101.23.111"],
            },
            "Peer": {
                "node-a": {
                    "HostName": "pentium",
                    "Online": pentium_online,
                    "TailscaleIPs": ["100.107.230.78"],
                },
                "node-b": {
                    "HostName": "core",
                    "Online": core_online,
                    "TailscaleIPs": ["100.97.105.116"],
                },
            },
        }

    def test_index_tailscale_status_includes_self_and_peers(self):
        indexed = health.index_tailscale_status(self.tailscale_status())
        self.assertTrue(indexed["x99"]["online"])
        self.assertEqual(indexed["pentium"]["ipv4"], "100.107.230.78")
        self.assertTrue(indexed["core"]["online"])

    def test_evaluate_marks_target_healthy_when_tailnet_and_ssh_are_up(self):
        result = health.evaluate_node(
            "pentium",
            self.inventory["nodes"]["pentium"],
            health.index_tailscale_status(self.tailscale_status()),
            tcp_probe=lambda host, port, timeout: True,
        )
        self.assertEqual(result["status"], "healthy")
        self.assertTrue(result["tailscale_online"])
        self.assertTrue(result["ssh_reachable"])

    def test_evaluate_degrades_when_tailnet_peer_is_offline(self):
        result = health.evaluate_node(
            "pentium",
            self.inventory["nodes"]["pentium"],
            health.index_tailscale_status(self.tailscale_status(pentium_online=False)),
            tcp_probe=lambda host, port, timeout: False,
        )
        self.assertEqual(result["status"], "degraded")
        self.assertFalse(result["tailscale_online"])
        self.assertFalse(result["ssh_reachable"])

    def test_load_inventory_rejects_missing_node_contract(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "inventory.json"
            path.write_text(
                json.dumps({"schema_version": 1, "nodes": {"pentium": {}}})
            )
            with self.assertRaises(ValueError):
                health.load_inventory(path)

    def test_summarize_ignores_optional_node_failure(self):
        results = [
            {"name": "pentium", "required": True, "status": "healthy"},
            {"name": "core", "required": True, "status": "healthy"},
            {"name": "x99", "required": False, "status": "degraded"},
        ]
        self.assertEqual(health.summarize(results)["status"], "healthy")

        results[1]["status"] = "degraded"
        self.assertEqual(health.summarize(results)["status"], "degraded")


class PortableOutputTests(unittest.TestCase):
    def test_render_text_is_ascii_safe(self):
        summary = {
            "status": "healthy",
            "nodes": [
                {
                    "name": "pentium",
                    "status": "healthy",
                    "tailscale_online": True,
                    "ipv4_matches": True,
                    "ssh_reachable": True,
                }
            ],
        }
        rendered = health.render_text(summary)
        rendered.encode("ascii")
        self.assertIn("ts=ok", rendered)
        self.assertIn("ssh=ok", rendered)


if __name__ == "__main__":
    unittest.main()
