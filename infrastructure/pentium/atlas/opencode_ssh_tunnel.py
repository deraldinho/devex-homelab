"""Build a private OpenCode SSH tunnel command without shell interpolation."""
from __future__ import annotations
import ipaddress
from dataclasses import dataclass

@dataclass(frozen=True)
class TunnelSpec:
    host: str = "x99"
    listen_port: int = 49375
    destination_port: int = 49374
    def command(self):
        if not (1 <= self.listen_port <= 65535 and 1 <= self.destination_port <= 65535):
            raise ValueError("invalid port")
        if not self.host or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for c in self.host):
            raise ValueError("invalid ssh host")
        return (
            "ssh", "-N", "-T", "-o", "BatchMode=yes",
            "-o", "ExitOnForwardFailure=yes",
            "-o", "ServerAliveInterval=20", "-o", "ServerAliveCountMax=3",
            "-o", "StrictHostKeyChecking=yes",
            "-L", f"127.0.0.1:{self.listen_port}:127.0.0.1:{self.destination_port}",
            self.host,
        )
    def endpoint(self):
        return f"http://127.0.0.1:{self.listen_port}"
