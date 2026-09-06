#!/usr/bin/env python3
"""Compatibility action backed by typed MANAGED READ."""

from __future__ import annotations

from typing import Any

try:
    from ..managed_read import ManagedReadOperation, ManagedReadService
except ImportError:
    from managed_read import ManagedReadOperation, ManagedReadService


def _degraded(error: str, detail: str) -> dict[str, Any]:
    return {"status": "degraded", "error": error, "detail": detail}


def collect_x99_status(service: ManagedReadService) -> dict[str, Any]:
    payload = service.read("x99", ManagedReadOperation.UPTIME)
    if payload.get("status") != "healthy":
        return {
            "status": "degraded",
            "error": str(payload.get("error", "managed-read-failed")),
            "detail": str(payload.get("detail", "")),
        }

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
