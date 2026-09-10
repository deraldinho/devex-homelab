import http.client
import json
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import atlas_dashboard


class FakeCollectors:
    @staticmethod
    def collect_status(config):
        return {"atlas": {"health": "healthy"}}

    @staticmethod
    def collect_events(config):
        return [{"source": "voice", "severity": "info", "message": "paused", "timestamp": "now"}]


class HttpContractTests(unittest.TestCase):
    def setUp(self):
        self.server = atlas_dashboard.build_server({"bind_host": "127.0.0.1", "bind_port": 0}, collectors=FakeCollectors)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=2)
        conn.request(method, path)
        res = conn.getresponse()
        body = res.read()
        conn.close()
        return res.status, dict(res.getheaders()), body

    def test_status_endpoint_is_json(self):
        status, headers, body = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["Content-Type"])
        self.assertEqual(json.loads(body)["atlas"]["health"], "healthy")

    def test_post_is_rejected_with_405(self):
        status, _, _ = self.request("POST", "/api/status")
        self.assertEqual(status, 405)

    def test_avatar_assets_are_served_read_only(self):
        assets = {
            "/assets/pixi.min.js": b"PIXI",
            "/assets/atlas-avatar-engine.js": b"AtlasAvatarEngine",
            "/assets/atlas-avatar-renderer.js": b"AtlasAvatarRenderer",
        }
        for path, marker in assets.items():
            status, headers, body = self.request("GET", path)
            self.assertEqual(status, 200, path)
            self.assertIn("application/javascript", headers["Content-Type"])
            self.assertIn(marker, body)
            post_status, _, _ = self.request("POST", path)
            self.assertEqual(post_status, 405, path)
