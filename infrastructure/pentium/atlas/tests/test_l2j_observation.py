import unittest
from unittest.mock import patch, MagicMock
import io
import json
try:
    from infrastructure.pentium.atlas.l2j_observation import L2jObservationService, L2jCapabilityExecutor
except ImportError:
    from atlas.l2j_observation import L2jObservationService, L2jCapabilityExecutor

class TestL2jObservation(unittest.TestCase):
    def test_probe_services_mocked(self):
        def fake_tcp(host, port, timeout):
            return port in (7777, 2106, 3306)

        def fake_http(url, timeout):
            if "query=" in url:
                return {
                    "status": "success",
                    "data": {
                        "result": [{"value": [1726830000, "1270000000"]}]
                    }
                }
            return None

        def fake_ssh(host, cmd, timeout):
            return "l2jtoren-gameserver:::Up 2 hours:::image:v1\nl2jtoren-loginserver:::Up 2 hours:::image:v1"

        svc = L2jObservationService(
            default_host="100.101.23.111",
            tcp_prober=fake_tcp,
            http_getter=fake_http,
            ssh_runner=fake_ssh
        )

        res = svc.get_summary()
        self.assertEqual("HEALTHY", res["probes"]["overall_status"])
        self.assertTrue(res["probes"]["services"]["gameserver_tcp"]["reachable"])
        self.assertTrue(res["probes"]["services"]["loginserver_tcp"]["reachable"])
        self.assertTrue(res["probes"]["services"]["database_mariadb"]["reachable"])
        self.assertEqual(2, res["docker"]["total_containers_found"])
        self.assertIn("l2jtoren-gameserver", res["docker"]["containers"])

        executor = L2jCapabilityExecutor(svc)
        out = executor("l2j_get_status", {})
        self.assertIn("L2jToren Organismo: HEALTHY", out["summary"])

        out_docker = executor("l2j_docker_stats", {})
        self.assertEqual(2, out_docker["total_containers_found"])

        out_jvm = executor("l2j_check_jvm", {})
        self.assertEqual("TELEMETRY_AVAILABLE", out_jvm["status"])
        self.assertIn("heap_used_mb", out_jvm)

    def test_grafana_dashboards_mocked(self):
        svc = L2jObservationService(default_host="100.101.23.111")
        mock_resp_data = [
            {"id": 1, "uid": "l2j-overview", "title": "L2j Overview", "type": "dash-db", "url": "/d/l2j-overview/l2j-overview"},
            {"id": 2, "uid": "l2j-runtime", "title": "L2j Runtime DB", "type": "dash-db", "url": "/d/l2j-runtime/l2j-runtime-db"},
            {"id": 3, "uid": "folder-1", "title": "L2j Folder", "type": "dash-folder", "url": "/dashboards/f/folder-1"},
        ]

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(mock_resp_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = svc.fetch_grafana_dashboards()
            self.assertEqual("AVAILABLE", res["status"])
            self.assertEqual(2, res["total_dashboards"])
            self.assertEqual("l2j-overview", res["dashboards"][0]["uid"])
            self.assertIn("3000/d/l2j-overview", res["dashboards"][0]["url"])

            executor = L2jCapabilityExecutor(svc)
            out = executor("l2j_get_dashboards", {})
            self.assertEqual("AVAILABLE", out["status"])
            self.assertEqual(2, out["total_dashboards"])

    def test_fetch_container_logs_and_capability(self):
        commands_run = []
        def fake_ssh(host, cmd, timeout):
            commands_run.append((host, cmd, timeout))
            if "l2jtoren-gameserver" in cmd:
                return "[INFO] GameServer ready on 7777\n[INFO] 0 players connected"
            return "unknown container"

        svc = L2jObservationService(
            default_host="100.101.23.111",
            ssh_runner=fake_ssh,
        )

        res = svc.fetch_container_logs("l2jtoren-gameserver", lines=20)
        self.assertTrue(res["ssh_available"])
        self.assertEqual("l2jtoren-gameserver", res["container"])
        self.assertEqual(20, res["lines_requested"])
        self.assertIn("GameServer ready on 7777", res["logs"])
        self.assertEqual("docker logs --tail 20 l2jtoren-gameserver", commands_run[-1][1])

        # Teste de sanitização de segurança (rejeita injeção de shell)
        malicious = svc.fetch_container_logs("gameserver; rm -rf /", lines=50)
        self.assertIn("Nome de container invalido", malicious["error"])

        # Teste de execução via capability
        executor = L2jCapabilityExecutor(svc)
        out = executor("l2j_get_logs", {"container": "l2jtoren-gameserver", "lines": 30})
        self.assertTrue(out["ssh_available"])
        self.assertEqual(30, out["lines_requested"])
        self.assertIn("GameServer ready", out["logs"])

    def test_heap_warning_threshold(self):
        def fake_tcp(host, port, timeout):
            return True

        def fake_http(url, timeout):
            # Retorna 95% de heap
            if "l2j_jvm_memory_heap_used_bytes" in url:
                return {"status": "success", "data": {"result": [{"value": [1726830000, "950000000"]}]}}
            if "l2j_jvm_memory_heap_committed_bytes" in url:
                return {"status": "success", "data": {"result": [{"value": [1726830000, "1000000000"]}]}}
            return None

        svc = L2jObservationService(
            default_host="100.101.23.111",
            tcp_prober=fake_tcp,
            http_getter=fake_http,
            ssh_runner=lambda h, c, t: "",
        )

        res = svc.get_summary()
        self.assertTrue(res["heap_warning"])
        self.assertIn("ALERTA: JVM Heap elevada", res["summary"])

if __name__ == "__main__":
    unittest.main()

