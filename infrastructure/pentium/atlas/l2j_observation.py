from __future__ import annotations

import json
import socket
import subprocess
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Optional

DEFAULT_L2J_HOST = "100.101.23.111"

L2J_PORT_SERVICES = {
    "gameserver_tcp": 7777,
    "gameserver_http": 8088,
    "loginserver_tcp": 2106,
    "database_mariadb": 3306,
    "prometheus": 9090,
    "grafana": 3000,
}


def default_tcp_probe(host: str, port: int, timeout_sec: float = 1.5) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout_sec)
            return sock.connect_ex((host, port)) == 0
    except Exception:
        return False


def default_http_get(url: str, timeout_sec: float = 2.0) -> Optional[dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Atlas-L2jObserver/1.0"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            if resp.status == 200:
                data = resp.read().decode("utf-8")
                return json.loads(data)
    except Exception:
        return None
    return None


def default_ssh_runner(host: str, command: str, timeout_sec: float = 5.0) -> Optional[str]:
    from pathlib import Path
    ssh_cmd = [
        "ssh",
        "-F", "/dev/null",
        "-o", "BatchMode=yes",
        "-o", "IdentitiesOnly=yes",
        "-o", "StrictHostKeyChecking=no",
        "-o", f"ConnectTimeout={max(1, int(timeout_sec))}",
    ]
    # Se for o host x99 e a chave existir, usa as credenciais dedicadas
    id_x99 = Path.home() / ".ssh" / "id_ed25519_x99_control"
    known_x99 = Path.home() / ".ssh" / "known_hosts_x99"
    if host == "100.101.23.111" and id_x99.exists():
        ssh_cmd.extend(["-i", str(id_x99)])
        if known_x99.exists():
            ssh_cmd.extend(["-o", f"UserKnownHostsFile={known_x99}"])

    ssh_cmd.extend([
        f"deral@{host}",
        command,
    ])
    try:
        res = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec + 1.0,
            check=False,
        )
        if res.returncode == 0:
            out = res.stdout.strip()
            if not out and res.stderr:
                err_lines = [line for line in res.stderr.splitlines() if not line.startswith("**")]
                out = "\n".join(err_lines).strip()
            return out
    except Exception:
        return None
    return None


class L2jObservationService:
    def __init__(
        self,
        default_host: str = DEFAULT_L2J_HOST,
        tcp_prober: Callable[[str, int, float], bool] = default_tcp_probe,
        http_getter: Callable[[str, float], Optional[dict]] = default_http_get,
        ssh_runner: Callable[[str, str, float], Optional[str]] = default_ssh_runner,
    ):
        self.default_host = default_host
        self.tcp_prober = tcp_prober
        self.http_getter = http_getter
        self.ssh_runner = ssh_runner

    def probe_services(self, host: Optional[str] = None) -> Dict[str, Any]:
        target_host = host or self.default_host
        results = {}
        all_ok = True
        critical_ok = True

        for name, port in L2J_PORT_SERVICES.items():
            is_up = self.tcp_prober(target_host, port, 1.5)
            results[name] = {
                "port": port,
                "reachable": is_up,
                "status": "UP" if is_up else "DOWN",
            }
            if name in ("gameserver_tcp", "loginserver_tcp", "database_mariadb") and not is_up:
                critical_ok = False
            if not is_up:
                all_ok = False

        return {
            "target_host": target_host,
            "overall_status": "HEALTHY" if critical_ok else "DEGRADED",
            "critical_services_online": critical_ok,
            "all_services_online": all_ok,
            "services": results,
        }

    def fetch_jvm_telemetry(self, prometheus_host: Optional[str] = None) -> Dict[str, Any]:
        target_host = prometheus_host or self.default_host
        prom_url = f"http://{target_host}:9090/api/v1/query"

        metrics = {
            "jvm_memory_used_bytes": None,
            "jvm_memory_committed_bytes": None,
            "jvm_threads_current": None,
            "process_cpu_pct": None,
            "db_connections_active": None,
            "status": "PROMETHEUS_UNREACHABLE",
        }

        queries = {
            "jvm_memory_used_bytes": 'l2j_jvm_memory_heap_used_bytes{exported_job="l2jtoren-gameserver"}',
            "jvm_memory_committed_bytes": 'l2j_jvm_memory_heap_committed_bytes{exported_job="l2jtoren-gameserver"}',
            "jvm_threads_current": 'l2j_jvm_threads_live{exported_job="l2jtoren-gameserver"}',
            "process_cpu_pct": 'l2j_process_cpu_load{exported_job="l2jtoren-gameserver"}',
            "db_connections_active": 'l2j_db_connections_active{exported_job="l2jtoren-gameserver"}',
        }

        # Fallback queries se as específicas do l2j não forem encontradas
        fallback_queries = {
            "jvm_memory_used_bytes": 'jvm_memory_bytes_used{area="heap"}',
            "jvm_memory_committed_bytes": 'jvm_memory_bytes_max{area="heap"}',
            "jvm_threads_current": 'jvm_threads_current',
        }

        any_found = False
        for metric_name, query_str in queries.items():
            encoded_query = urllib.parse.quote(query_str)
            full_url = f"{prom_url}?query={encoded_query}"
            res = self.http_getter(full_url, 1.5)
            if res and res.get("status") == "success":
                data = res.get("data", {}).get("result", [])
                if data and len(data) > 0:
                    first_entry = data[0]
                    if isinstance(first_entry, dict):
                        val = first_entry.get("value", [None, None])[1]
                    elif isinstance(first_entry, (list, tuple)) and len(first_entry) > 1:
                        val = first_entry[1]
                    else:
                        val = None
                    try:
                        metrics[metric_name] = float(val)
                        any_found = True
                    except (ValueError, TypeError):
                        pass

        # Executa fallback se necessário
        if not any_found:
            for metric_name, query_str in fallback_queries.items():
                encoded_query = urllib.parse.quote(query_str)
                full_url = f"{prom_url}?query={encoded_query}"
                res = self.http_getter(full_url, 1.5)
                if res and res.get("status") == "success":
                    data = res.get("data", {}).get("result", [])
                    if data and len(data) > 0:
                        first_entry = data[0]
                        if isinstance(first_entry, dict):
                            val = first_entry.get("value", [None, None])[1]
                        elif isinstance(first_entry, (list, tuple)) and len(first_entry) > 1:
                            val = first_entry[1]
                        else:
                            val = None
                        try:
                            metrics[metric_name] = float(val)
                            any_found = True
                        except (ValueError, TypeError):
                            pass

        if any_found:
            metrics["status"] = "TELEMETRY_AVAILABLE"
            used = metrics.get("jvm_memory_used_bytes")
            comm = metrics.get("jvm_memory_committed_bytes")
            if used:
                metrics["heap_used_mb"] = round(used / (1024 * 1024), 1)
            if comm:
                metrics["heap_committed_mb"] = round(comm / (1024 * 1024), 1)
            if used and comm and comm > 0:
                metrics["heap_usage_pct"] = round((used / comm) * 100.0, 1)
            if metrics.get("process_cpu_pct") is not None:
                metrics["process_cpu_pct"] = round(metrics["process_cpu_pct"] * 100.0, 1)

        return metrics

    def fetch_grafana_dashboards(self, host: Optional[str] = None, auth: tuple[str, str] = ("admin", "admin")) -> Dict[str, Any]:
        target_host = host or self.default_host
        url = f"http://{target_host}:3000/api/search"
        import base64
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Atlas-L2jObserver/1.0"})
            cred = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
            req.add_header("Authorization", f"Basic {cred}")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    items = json.loads(resp.read().decode("utf-8"))
                    dashboards = []
                    for item in items:
                        if item.get("type") == "dash-db":
                            dashboards.append({
                                "title": item.get("title"),
                                "uid": item.get("uid"),
                                "url": f"http://{target_host}:3000{item.get('url')}",
                            })
                    return {
                        "host": target_host,
                        "status": "AVAILABLE",
                        "total_dashboards": len(dashboards),
                        "dashboards": dashboards,
                    }
        except Exception as exc:
            return {
                "host": target_host,
                "status": "UNAVAILABLE",
                "error": str(exc),
                "dashboards": [],
            }
        return {"host": target_host, "status": "UNAVAILABLE", "dashboards": []}

    def fetch_docker_status(self, host: Optional[str] = None) -> Dict[str, Any]:
        target_host = host or self.default_host
        # Executa inspeção rápida dos containers l2jtoren via SSH
        cmd = 'docker ps --filter "name=l2jtoren" --format "{{.Names}}:::{{.Status}}:::{{.Image}}"'
        out = self.ssh_runner(target_host, cmd, 5.0)
        containers = {}
        if out:
            for line in out.splitlines():
                parts = line.strip().split(":::") if ":::" in line else line.strip().split("|")
                if len(parts) >= 2:
                    name = parts[0]
                    status = parts[1]
                    image = parts[2] if len(parts) > 2 else "unknown"
                    containers[name] = {"status": status, "image": image}

        return {
            "host": target_host,
            "ssh_available": bool(out is not None),
            "total_containers_found": len(containers),
            "containers": containers,
        }

    def fetch_container_logs(
        self,
        container: str = "l2jtoren-gameserver",
        lines: int = 50,
        host: Optional[str] = None,
    ) -> Dict[str, Any]:
        import re
        target_host = host or self.default_host
        container_str = str(container or "l2jtoren-gameserver").strip()
        if not re.match(r"^[a-zA-Z0-9_\.\-]+$", container_str):
            return {
                "host": target_host,
                "container": container_str,
                "error": "Nome de container invalido para execucao segura",
                "logs": "",
            }
        try:
            num_lines = max(1, min(int(lines), 500))
        except (ValueError, TypeError):
            num_lines = 50

        cmd = f"docker logs --tail {num_lines} {container_str}"
        out = self.ssh_runner(target_host, cmd, 5.0)
        return {
            "host": target_host,
            "container": container_str,
            "lines_requested": num_lines,
            "ssh_available": bool(out is not None),
            "logs": out if out is not None else "",
            "error": None if out is not None else "Falha ao obter logs via SSH ou container inexistente",
        }

    def get_summary(self, host: Optional[str] = None) -> Dict[str, Any]:
        probe_info = self.probe_services(host)
        jvm_info = self.fetch_jvm_telemetry(host)
        docker_info = self.fetch_docker_status(host)

        gameserver_up = probe_info["services"]["gameserver_tcp"]["reachable"]
        loginserver_up = probe_info["services"]["loginserver_tcp"]["reachable"]
        db_up = probe_info["services"]["database_mariadb"]["reachable"]

        heap_pct = jvm_info.get("heap_usage_pct")
        heap_warning = False
        if heap_pct is not None:
            try:
                heap_warning = float(heap_pct) >= 90.0
            except (ValueError, TypeError):
                pass

        summary_text = (
            f"L2jToren Organismo: {probe_info['overall_status']} | "
            f"GameServer(7777): {'UP' if gameserver_up else 'DOWN'} | "
            f"LoginServer(2106): {'UP' if loginserver_up else 'DOWN'} | "
            f"MariaDB(3306): {'UP' if db_up else 'DOWN'}"
        )
        if docker_info.get("total_containers_found", 0) > 0:
            summary_text += f" | Containers Docker ativos: {docker_info['total_containers_found']}"
        if jvm_info.get("heap_used_mb"):
            summary_text += f" | GameServer Heap: {jvm_info['heap_used_mb']}MB/{jvm_info.get('heap_committed_mb', '?')}MB ({jvm_info.get('heap_usage_pct', '?')}%)"
        elif jvm_info.get("heap_usage_pct"):
            summary_text += f" | JVM Heap: {jvm_info['heap_usage_pct']}%"
        if heap_warning:
            summary_text += f" [ALERTA: JVM Heap elevada ({heap_pct}%)]"
        if jvm_info.get("jvm_threads_current"):
            summary_text += f" | Threads: {int(jvm_info['jvm_threads_current'])}"
        if jvm_info.get("process_cpu_pct") is not None:
            summary_text += f" | CPU: {jvm_info['process_cpu_pct']}%"
        if jvm_info.get("db_connections_active") is not None:
            summary_text += f" | DB Conns: {int(jvm_info['db_connections_active'])}"

        return {
            "summary": summary_text,
            "probes": probe_info,
            "jvm": jvm_info,
            "docker": docker_info,
            "heap_warning": heap_warning,
        }


class L2jCapabilityExecutor:
    def __init__(self, observation_service: Optional[L2jObservationService] = None):
        self.service = observation_service or L2jObservationService()

    def __call__(self, capability: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        host = params.get("host")

        if capability == "l2j_get_status":
            return self.service.get_summary(host=host)
        elif capability == "l2j_get_dashboards":
            return self.service.fetch_grafana_dashboards(host=host)
        elif capability == "l2j_check_jvm":
            return self.service.fetch_jvm_telemetry(prometheus_host=host)
        elif capability == "l2j_docker_stats":
            return self.service.fetch_docker_status(host=host)
        elif capability == "l2j_probe_ports":
            return self.service.probe_services(host=host)
        elif capability == "l2j_get_logs":
            container = str(params.get("container") or "l2jtoren-gameserver")
            lines = params.get("lines", 50)
            return self.service.fetch_container_logs(container=container, lines=lines, host=host)
        else:
            return {"error": f"Capacidade L2j desconhecida: {capability}"}

