#!/usr/bin/env python3
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import dashboard_collectors


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    server_version = "AtlasDashboard/1"

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        if len(body) > 262144:
            body = b'{"error":"response_too_large"}'
            status = 503
            content_type = "application/json; charset=utf-8"
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        collectors = self.server.collectors
        config = self.server.config
        if self.path == "/healthz":
            self._send(200, "application/json; charset=utf-8", b'{"status":"ok"}')
            return
        if self.path == "/api/status":
            body = json.dumps(collectors.collect_status(config), ensure_ascii=True).encode()
            self._send(200, "application/json; charset=utf-8", body)
            return
        if self.path == "/api/events":
            body = json.dumps(collectors.collect_events(config), ensure_ascii=True).encode()
            self._send(200, "application/json; charset=utf-8", body)
            return
        if self.path == "/":
            body = Path(__file__).with_name("dashboard.html").read_bytes()
            self._send(200, "text/html; charset=utf-8", body)
            return
        self._send(404, "application/json; charset=utf-8", b'{"error":"not_found"}')

    def _method_not_allowed(self) -> None:
        self._send(405, "application/json; charset=utf-8", b'{"error":"method_not_allowed"}')

    do_POST = _method_not_allowed
    do_PUT = _method_not_allowed
    do_PATCH = _method_not_allowed
    do_DELETE = _method_not_allowed

    def log_message(self, fmt: str, *args) -> None:
        return


def build_server(config: dict, *, collectors=dashboard_collectors) -> DashboardServer:
    server = DashboardServer((config["bind_host"], int(config["bind_port"])), Handler)
    server.config = config
    server.collectors = collectors
    return server


def main() -> int:
    config = dashboard_collectors.load_config(Path(__file__).with_name("config.json"))
    server = build_server(config)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
