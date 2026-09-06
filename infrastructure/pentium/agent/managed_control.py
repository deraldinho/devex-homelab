#!/usr/bin/env python3
"""Typed, allowlisted CONTROL operations for MANAGED hosts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from .control_audit import ControlAuditRecord
from .managed_inventory import ManagedHost, ManagedInventory
from .ssh_transport import SshTarget, SshTransport


class ManagedControlOperation(str, Enum):
    START_SERVICE = "start_service"
    STOP_SERVICE = "stop_service"
    RESTART_SERVICE = "restart_service"
    REBOOT_HOST = "reboot_host"


_SERVICE_OPERATIONS = {
    ManagedControlOperation.START_SERVICE,
    ManagedControlOperation.STOP_SERVICE,
    ManagedControlOperation.RESTART_SERVICE,
}


@dataclass(frozen=True)
class ControlAuthorization:
    authorized: bool
    host_id: str
    operation: ManagedControlOperation
    target: str | None = None
    human_confirmed: bool = False
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.host_id.strip():
            raise ValueError("host_id is required")
        if not isinstance(self.operation, ManagedControlOperation):
            raise TypeError("operation must be ManagedControlOperation")
        if self.target is not None and not self.target.strip():
            raise ValueError("target cannot be blank")


def _ssh_target(host: ManagedHost) -> SshTarget:
    return SshTarget(
        user=host.user,
        host=host.host,
        identity_file=host.identity_file,
        known_hosts_file=host.known_hosts_file,
        connect_timeout_seconds=host.connect_timeout_seconds,
        max_output_bytes=host.max_output_bytes,
    )


def _linux_command(operation: ManagedControlOperation, target: str | None) -> str:
    if operation is ManagedControlOperation.REBOOT_HOST:
        return "systemctl reboot"
    verb = operation.value.removesuffix("_service")
    return f"systemctl {verb} {target}"

def _windows_command(operation: ManagedControlOperation, target: str | None) -> str:
    if operation is ManagedControlOperation.REBOOT_HOST:
        return 'powershell.exe -NoProfile -NonInteractive -Command "Restart-Computer -Force"'
    verbs = {
        ManagedControlOperation.START_SERVICE: "Start-Service",
        ManagedControlOperation.STOP_SERVICE: "Stop-Service",
        ManagedControlOperation.RESTART_SERVICE: "Restart-Service",
    }
    return (
        'powershell.exe -NoProfile -NonInteractive -Command '
        f'"{verbs[operation]} -Name \'{target}\'"'
    )


class ManagedControlService:
    def __init__(self, inventory: ManagedInventory, transport: SshTransport, audit_sink):
        self._inventory = inventory
        self._transport = transport
        self._audit_sink = audit_sink

    def _audit(self, authorization: ControlAuthorization, *, phase: str, status: str, reason: str) -> None:
        self._audit_sink.append(ControlAuditRecord(
            timestamp=datetime.now(timezone.utc),
            phase=phase,
            host_id=authorization.host_id,
            operation=authorization.operation.value,
            target=authorization.target,
            authorized=authorization.authorized,
            status=status,
            reason=reason,
        ))

    def execute(self, authorization: ControlAuthorization) -> dict[str, object]:
        if not authorization.authorized:
            raise PermissionError("control authorization denied")
        host = self._inventory.require_managed(authorization.host_id)
        if authorization.operation.value not in host.allowed_controls:
            raise PermissionError("control operation not allowlisted")
        if authorization.operation in _SERVICE_OPERATIONS:
            if authorization.target not in host.allowed_services:
                raise PermissionError("service target not allowlisted")
        elif not authorization.human_confirmed:
            raise PermissionError("human confirmation required")

        self._audit(authorization, phase="attempt", status="authorized", reason=authorization.reason)
        command = (
            _windows_command(authorization.operation, authorization.target)
            if host.platform.lower() == "windows"
            else _linux_command(authorization.operation, authorization.target)
        )
        result = self._transport.run(_ssh_target(host), command)
        status = "success" if result.returncode == 0 else "degraded"
        self._audit(authorization, phase="result", status=status, reason=result.error or "completed")
        if result.returncode != 0:
            return {
                "status": "degraded",
                "host": host.host_id,
                "operation": authorization.operation.value,
                "target": authorization.target,
                "error": result.error or "ssh-failed",
            }
        return {
            "status": "success",
            "host": host.host_id,
            "operation": authorization.operation.value,
            "target": authorization.target,
        }
