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

    def test_query_string_does_not_change_route_resolution(self):
        status, headers, body = self.request("GET", "/?v=eab9893")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"Atlas Observability Dashboard", body)

        status, headers, body = self.request("GET", "/assets/atlas-avatar-engine.js?v=eab9893")
        self.assertEqual(status, 200)
        self.assertIn("application/javascript", headers["Content-Type"])
        self.assertIn(b"AtlasAvatarEngine", body)

    def test_post_is_rejected_with_405(self):
        status, _, _ = self.request("POST", "/api/status")
        self.assertEqual(status, 405)

    def test_repository_avatar_assets_are_served_read_only(self):
        for path, marker in (
            ("/assets/atlas-avatar-engine.js", b"AtlasAvatarEngine"),
            ("/assets/atlas-avatar-renderer.js", b"AtlasAvatarRenderer"),
        ):
            status, headers, body = self.request("GET", path)
            self.assertEqual(status, 200, path)
            self.assertIn("application/javascript", headers["Content-Type"])
            self.assertIn(marker, body)
            post_status, _, _ = self.request("POST", path)
            self.assertEqual(post_status, 405, path)

    def test_missing_runtime_pixi_asset_degrades_to_404(self):
        pixi = ROOT / "pixi.min.js"
        if pixi.exists():
            self.skipTest("pixi runtime asset already provisioned")
        status, headers, body = self.request("GET", "/assets/pixi.min.js")
        self.assertEqual(status, 404)
        self.assertIn("application/json", headers["Content-Type"])
        self.assertEqual(json.loads(body)["error"], "asset_not_found")

    def test_repository_anime_sprites_are_served_read_only(self):
        for path in (
            "/assets/atlas-pet-standing.png",
            "/assets/atlas-pet-sitting.png",
            "/assets/atlas-pet-poke.png",
        ):
            status, headers, body = self.request("GET", path)
            self.assertEqual(status, 200, path)
            self.assertIn("image/png", headers["Content-Type"])
            self.assertTrue(body.startswith(b"\x89PNG\r\n\x1a\n"), f"PNG magic bytes mismatch for {path}")
            self.assertGreater(len(body), 50000, f"Sprite asset too small for {path}")
            post_status, _, _ = self.request("POST", path)
            self.assertEqual(post_status, 405, path)


if __name__ == "__main__":
    unittest.main()
