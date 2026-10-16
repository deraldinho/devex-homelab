"""CP26 P0: only loopback/SSH-forward peers may submit chats.

Read endpoints remain on LAN; X-Forwarded-For and other client headers do
not grant authority. Production requires SSH tunnel to submit /api/chat.
"""
from __future__ import annotations

import json
import http.client
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import atlas_dashboard


class FakeCollectors:
    @staticmethod
    def collect_status(config):
        return {}

    @staticmethod
    def collect_events(config):
        return []


class PeerAuthorizationTests(unittest.TestCase):
    def test_only_loopback_network_peers_authorized(self):
        for address, expected in (
            ("127.0.0.1", True),
            ("127.42.15.1", True),
            ("::1", True),
            ("192.168.88.3", True),
            ("192.168.88.10", False),
            ("10.10.0.4", False),
            ("0.0.0.0", False),
            ("8.8.8.8", False),
            ("::ffff:127.0.0.1", False),
            ("malformed", False),
            ("", False),
        ):
            with self.subTest(address=address):
                request = SimpleNamespace(
                    client_address=(address, 1234),
                    server=SimpleNamespace(server_address=("192.168.88.3", 8765)),
                    headers={
                    "X-Forwarded-For": "127.0.0.1",
                    "X-Real-IP": "127.0.0.1",
                    "Origin": "http://127.0.0.1",
                })
                self.assertEqual(expected, atlas_dashboard.Handler._chat_peer_authorized(request))

    def test_simulated_remote_peer_gets_403_without_queue_write(self):
        class RemotePeerHandler(atlas_dashboard.Handler):
            def setup(self):
                super().setup()
                self.client_address = ("192.168.88.10", 10021)

        with TemporaryDirectory() as tmp:
            queue = Path(tmp) / "chat-inbox.json"
            server = atlas_dashboard.build_server({
                "bind_host": "127.0.0.1", "bind_port": 0,
                "chat_inbox_path": str(queue),
            }, collectors=FakeCollectors)
            server.RequestHandlerClass = RemotePeerHandler
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                conn = http.client.HTTPConnection(*server.server_address, timeout=2)
                conn.request(
                    "POST", "/api/chat",
                    body=json.dumps({"message": "Nao autorizado",
                                     "client_message_id": "remote"}),
                    headers={"Content-Type": "application/json",
                             "X-Forwarded-For": "127.0.0.1",
                             "Origin": "http://127.0.0.1"},
                )
                res = conn.getresponse()
                body = json.loads(res.read())
                conn.close()
                self.assertEqual(403, res.status)
                self.assertEqual("chat_requires_local_ssh_tunnel", body["error"])
                self.assertFalse(queue.exists())
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)

    def test_loopback_post_remains_functional_and_idempotent(self):
        with TemporaryDirectory() as tmp:
            server = atlas_dashboard.build_server({
                "bind_host": "127.0.0.1", "bind_port": 0,
                "chat_inbox_path": str(Path(tmp) / "inbox.json"),
            }, collectors=FakeCollectors)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                def post():
                    conn = http.client.HTTPConnection(*server.server_address, timeout=2)
                    conn.request("POST", "/api/chat",
                                 body=json.dumps({"message": "Oi Atlas",
                                                  "client_message_id": "cp26-peer1"}),
                                 headers={"Content-Type": "application/json",
                                          "X-Forwarded-For": "198.51.100.2"})
                    reply = conn.getresponse()
                    code, raw = reply.status, reply.read()
                    conn.close()
                    return code, json.loads(raw)
                first, body = post()
                second, repeated = post()
                self.assertEqual((202, 202), (first, second))
                self.assertEqual(body["message_id"], repeated["message_id"])
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
