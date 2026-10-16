#!/usr/bin/env python3
from __future__ import annotations

import json
from ipaddress import ip_address
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import dashboard_collectors
from dashboard_event_store import DashboardEventStore
from dashboard_chat import DashboardChatGateway


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    server_version = "AtlasDashboard/1"

    def _send(self, status: int, content_type: str, body: bytes, *, max_bytes: int = 262144) -> None:
        if len(body) > max_bytes:
            body = b'{"error":"response_too_large"}'
            status = 503
            content_type = "application/json; charset=utf-8"
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def _send_asset(self, filename: str) -> None:
        path = Path(__file__).with_name(filename)
        if not path.is_file():
            self._send(404, "application/json; charset=utf-8", b'{"error":"asset_not_found"}')
            return
        ctype = "image/png" if filename.endswith(".png") else "application/javascript; charset=utf-8"
        self._send(200, ctype, path.read_bytes(), max_bytes=4194304)

    def do_GET(self) -> None:
        collectors = self.server.collectors
        config = self.server.config
        request_path = urlsplit(self.path).path
        if request_path == "/healthz":
            self._send(200, "application/json; charset=utf-8", b'{"status":"ok"}')
            return
        if request_path == "/api/status":
            body = json.dumps(collectors.collect_status(config), ensure_ascii=True).encode()
            self._send(200, "application/json; charset=utf-8", body)
            return
        if request_path == "/api/events":
            body = json.dumps(collectors.collect_events(config), ensure_ascii=True).encode()
            self._send(200, "application/json; charset=utf-8", body)
            return
        if request_path == "/api/stream":
            raw=self.headers.get("Last-Event-ID","0")
            try: last_id=max(0,int(raw))
            except ValueError: last_id=0
            store=DashboardEventStore(Path(config.get("dashboard_events_path","~/pentium-agent/atlas/runtime/dashboard-events.jsonl")).expanduser())
            chunks=[]
            for event in store.after(last_id):
                chunks.append(f"id: {event['id']}\nevent: {event.get('type','message')}\ndata: {json.dumps(event.get('payload',{}),ensure_ascii=True,separators=(',',':'))}\n\n")
            if not chunks: chunks.append(": heartbeat\n\n")
            self._send(200,"text/event-stream; charset=utf-8","".join(chunks).encode(),max_bytes=262144)
            return
        assets = {
            "/assets/pixi.min.js": "pixi.min.js",
            "/assets/atlas-avatar-motion.js": "atlas-avatar-motion.js",
            "/assets/atlas-avatar-engine.js": "atlas-avatar-engine.js",
            "/assets/atlas-avatar-renderer.js": "atlas-avatar-renderer.js",
            "/assets/atlas-pet-standing.png": "atlas-pet-standing.png",
            "/assets/atlas-pet-sitting.png": "atlas-pet-sitting.png",
            "/assets/atlas-pet-poke.png": "atlas-pet-poke.png",
        }
        if request_path in assets:
            self._send_asset(assets[request_path])
            return
        if request_path == "/":
            body = Path(__file__).with_name("dashboard.html").read_bytes()
            self._send(200, "text/html; charset=utf-8", body)
            return
        self._send(404, "application/json; charset=utf-8", b'{"error":"not_found"}')

    def _method_not_allowed(self) -> None:
        self._send(405, "application/json; charset=utf-8", b'{"error":"method_not_allowed"}')

    def _chat_peer_authorized(self) -> bool:
        # Only local processes / encrypted SSH forward can submit chat.
        # Do not trust X-Forwarded-For or Origin from anonymous LAN clients.
        try:
            address = ip_address(self.client_address[0])
        except (ValueError, IndexError, TypeError, AttributeError):
            return False
        if getattr(address, 'ipv4_mapped', None):
            return False
        if address.is_loopback:
            return True
        # SSH -L to a LAN-bound listener on Pentium uses the host LAN
        # address as TCP source, verified via `ip route get <bind_host>`.
        # A remote LAN peer cannot establish a TCP connection using the
        # server's own local address unless the host/network is compromised.
        try:
            bound = ip_address(self.server.server_address[0])
        except (ValueError, IndexError, TypeError, AttributeError):
            return False
        return address == bound and not bound.is_unspecified

    def do_POST(self) -> None:
        request_path=urlsplit(self.path).path
        if request_path!="/api/chat":
            self._method_not_allowed(); return
        if not self._chat_peer_authorized():
            self._send(403, "application/json; charset=utf-8",
                       b'{"error":"chat_requires_local_ssh_tunnel"}')
            return
        if self.headers.get("Content-Type","").split(";",1)[0].strip().lower()!="application/json":
            self._send(415,"application/json; charset=utf-8",b'{"error":"unsupported_media_type"}'); return
        try: length=int(self.headers.get("Content-Length","0"))
        except ValueError: length=0
        if length<=0 or length>4096:
            self._send(413,"application/json; charset=utf-8",b'{"error":"request_too_large"}'); return
        try:
            payload=json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload,dict) or set(payload)!={"message","client_message_id"}: raise ValueError("invalid_fields")
            gateway=DashboardChatGateway(Path(self.server.config.get("chat_inbox_path","~/pentium-agent/atlas/runtime/chat-inbox.json")).expanduser())
            result=gateway.submit(payload["message"],payload["client_message_id"])
        except UnicodeDecodeError:
            self._send(400,"application/json; charset=utf-8",b'{"error":"invalid_utf8"}'); return
        except OverflowError:
            self._send(429,"application/json; charset=utf-8",b'{"error":"chat_inbox_full"}'); return
        except (ValueError,TypeError,json.JSONDecodeError) as exc:
            code=413 if "max_message_chars" in str(exc) or "exceeds" in str(exc) else 400
            self._send(code,"application/json; charset=utf-8",json.dumps({"error":str(exc)[:128]},ensure_ascii=True).encode()); return
        self._send(202,"application/json; charset=utf-8",json.dumps(result,ensure_ascii=True,separators=(",",":")).encode())
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
