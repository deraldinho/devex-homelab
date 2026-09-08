from __future__ import annotations

from collections import deque
import json
import os
from pathlib import Path
import socket

from .modelo_visual_atlas import EstadoInteracaoVisual

MAX_DATAGRAM_BYTES = 512
_ALLOWED_KEYS = {
    "schema_version", "ouvindo", "pensando", "falando",
    "duvida_identidade", "atualizado_em",
}


def encode_interaction(state: EstadoInteracaoVisual) -> bytes:
    payload = {
        "schema_version": 1,
        "ouvindo": state.ouvindo,
        "pensando": state.pensando,
        "falando": state.falando,
        "duvida_identidade": state.duvida_identidade,
        "atualizado_em": state.atualizado_em,
    }
    raw = json.dumps(payload, ensure_ascii=True, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_DATAGRAM_BYTES:
        raise ValueError("interaction datagram exceeds bound")
    return raw


def decode_interaction(raw: bytes) -> EstadoInteracaoVisual:
    if len(raw) > MAX_DATAGRAM_BYTES:
        raise ValueError("interaction datagram exceeds bound")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or set(payload) != _ALLOWED_KEYS:
        raise ValueError("interaction datagram keys invalid")
    if payload.get("schema_version") != 1:
        raise ValueError("interaction schema_version must be 1")
    for key in ("ouvindo", "pensando", "falando", "duvida_identidade"):
        if not isinstance(payload[key], bool):
            raise ValueError("interaction flags must be bool")
    return EstadoInteracaoVisual(
        ouvindo=payload["ouvindo"],
        pensando=payload["pensando"],
        falando=payload["falando"],
        duvida_identidade=payload["duvida_identidade"],
        atualizado_em=payload["atualizado_em"],
    )


class InteractionDatagramClient:
    def __init__(self, path: Path):
        self._path = Path(path).expanduser()

    def send(self, state: EstadoInteracaoVisual) -> bool:
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            try:
                sock.sendto(encode_interaction(state), str(self._path))
            finally:
                sock.close()
            return True
        except (OSError, ValueError, AttributeError):
            return False


class InteractionDatagramListener:
    def __init__(self, path: Path, sink, *, error_capacity: int = 16):
        if error_capacity <= 0:
            raise ValueError("error_capacity must be > 0")
        self._path = Path(path).expanduser()
        self._sink = sink
        self._sock = None
        self._errors = deque(maxlen=error_capacity)

    def errors(self) -> tuple[str, ...]:
        return tuple(self._errors)

    def start(self) -> None:
        if self._sock is not None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.unlink(missing_ok=True)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            sock.bind(str(self._path))
            if os.name == "posix":
                os.chmod(self._path, 0o600)
        except Exception:
            sock.close()
            self._path.unlink(missing_ok=True)
            raise
        self._sock = sock

    def run_once(self, *, timeout_s: float = 0.2) -> bool:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be > 0")
        self.start()
        self._sock.settimeout(timeout_s)
        try:
            raw = self._sock.recv(MAX_DATAGRAM_BYTES + 1)
        except socket.timeout:
            return False
        try:
            state = decode_interaction(raw)
            self._sink(state)
            return True
        except Exception as exc:
            self._errors.append(f"interaction:{type(exc).__name__}")
            return False

    def close(self) -> None:
        sock, self._sock = self._sock, None
        if sock is not None:
            sock.close()
        self._path.unlink(missing_ok=True)
