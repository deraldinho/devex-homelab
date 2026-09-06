from __future__ import annotations

import json
import socket
from pathlib import Path


def _request_json_unix(socket_path: Path, method: str, path: str, body: bytes, timeout_s: float, max_response_bytes: int):
    if max_response_bytes <= 0:
        raise ValueError("max_response_bytes deve ser > 0")
    headers = [f"{method} {path} HTTP/1.1", "Host: localhost", "Connection: close"]
    if body:
        headers.extend(["Content-Type: application/json", f"Content-Length: {len(body)}"])
    request = ("\r\n".join(headers) + "\r\n\r\n").encode("ascii") + body
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout_s)
    try:
        sock.connect(str(socket_path))
        sock.sendall(request)
        raw = bytearray()
        while True:
            chunk = sock.recv(min(65536, max_response_bytes + 1))
            if not chunk:
                break
            raw.extend(chunk)
            if len(raw) > max_response_bytes:
                raise ValueError("resposta excede max_response_bytes")
    finally:
        sock.close()
    head, sep, body_raw = bytes(raw).partition(b"\r\n\r\n")
    if not sep:
        raise ValueError("resposta HTTP invalida")
    status = int(head.split(b" ", 2)[1])
    return status, json.loads(body_raw.decode("utf-8"))


def get_json_unix(socket_path: Path, path: str, timeout_s: float, max_response_bytes: int):
    return _request_json_unix(socket_path, "GET", path, b"", timeout_s, max_response_bytes)


def post_json_unix(socket_path: Path, path: str, payload: dict, timeout_s: float, max_response_bytes: int):
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return _request_json_unix(socket_path, "POST", path, body, timeout_s, max_response_bytes)
