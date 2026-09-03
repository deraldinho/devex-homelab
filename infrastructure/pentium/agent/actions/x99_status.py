#!/usr/bin/env python3
"""Implementation of the allowlisted x99.status action."""

from __future__ import annotations

import json
from typing import Any

from ssh_transport import SshTarget, SshTransport


REMOTE_STATUS_COMMAND = (
    'powershell.exe -NoProfile -NonInteractive -Command '
    '"$os=Get-CimInstance Win32_OperatingSystem; '
    '$boot=$os.LastBootUpTime; $now=Get-Date; '
    '[ordered]@{hostname=[Environment]::MachineName; '
    'user=[Environment]::UserName; '
    'last_boot=$boot.ToUniversalTime().ToString(\'o\'); '
    'uptime_seconds=[int][Math]::Floor(($now-$boot).TotalSeconds)} '
    '| ConvertTo-Json -Compress"'
)


def _degraded(error: str, detail: str) -> dict[str, Any]:
    return {
        "status": "degraded",
        "error": error,
        "detail": detail,
    }
def collect_x99_status(
    transport: SshTransport,
    target: SshTarget,
) -> dict[str, Any]:
    result = transport.run(target, REMOTE_STATUS_COMMAND)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit={result.returncode}"
        return _degraded(result.error or "ssh-failed", detail)

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return _degraded("invalid-json", str(exc))

    hostname = str(payload.get("hostname", ""))
    if hostname.lower() != "x99":
        return _degraded("unexpected-host", f"hostname={hostname or 'missing'}")

    try:
        uptime_seconds = int(payload["uptime_seconds"])
    except (KeyError, TypeError, ValueError):
        return _degraded("invalid-payload", "uptime_seconds")

    return {
        "status": "healthy",
        "hostname": hostname,
        "user": str(payload.get("user", "")),
        "last_boot": str(payload.get("last_boot", "")),
        "uptime_seconds": uptime_seconds,
    }
