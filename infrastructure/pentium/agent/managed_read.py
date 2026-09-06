#!/usr/bin/env python3
"""Typed, allowlisted READ operations for MANAGED hosts."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

try:
    from .managed_inventory import ManagedHost, ManagedInventory
    from .ssh_transport import SshResult, SshTarget, SshTransport
except ImportError:
    from managed_inventory import ManagedHost, ManagedInventory
    from ssh_transport import SshResult, SshTarget, SshTransport


class ManagedReadOperation(str, Enum):
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    UPTIME = "uptime"
    TEMPERATURE = "temperature"
    SERVICES = "services"
    PROCESSES = "processes"
    NETWORK = "network"
    CONTAINERS = "containers"
    LOGS = "logs"


WINDOWS_COMMANDS = {
    ManagedReadOperation.UPTIME: "powershell.exe -NoProfile -NonInteractive -Command \"$os=Get-CimInstance Win32_OperatingSystem; @{uptime_seconds=[int][Math]::Floor(((Get-Date)-$os.LastBootUpTime).TotalSeconds)} | ConvertTo-Json -Compress\"",
    ManagedReadOperation.MEMORY: "powershell.exe -NoProfile -NonInteractive -Command \"$os=Get-CimInstance Win32_OperatingSystem; @{total_bytes=[int64]$os.TotalVisibleMemorySize*1024; available_bytes=[int64]$os.FreePhysicalMemory*1024} | ConvertTo-Json -Compress\"",
    ManagedReadOperation.CPU: "powershell.exe -NoProfile -NonInteractive -Command \"@{cpu_percent=[double](Get-CimInstance Win32_Processor | Measure-Object LoadPercentage -Average).Average} | ConvertTo-Json -Compress\"",
}
WINDOWS_COMMANDS.update({
    ManagedReadOperation.DISK: "powershell.exe -NoProfile -NonInteractive -Command \"Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,Size,FreeSpace | ConvertTo-Json -Compress\"",
    ManagedReadOperation.TEMPERATURE: "powershell.exe -NoProfile -NonInteractive -Command \"Get-CimInstance -Namespace root/wmi MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue | Select-Object CurrentTemperature | ConvertTo-Json -Compress\"",
    ManagedReadOperation.SERVICES: "powershell.exe -NoProfile -NonInteractive -Command \"Get-Service | Select-Object -First 50 Name,Status | ConvertTo-Json -Compress\"",
    ManagedReadOperation.PROCESSES: "powershell.exe -NoProfile -NonInteractive -Command \"Get-Process | Sort-Object CPU -Descending | Select-Object -First 20 ProcessName,Id,CPU,WorkingSet64 | ConvertTo-Json -Compress\"",
    ManagedReadOperation.NETWORK: "powershell.exe -NoProfile -NonInteractive -Command \"Get-NetIPConfiguration | Select-Object InterfaceAlias,IPv4Address,IPv4DefaultGateway | ConvertTo-Json -Compress\"",
    ManagedReadOperation.CONTAINERS: "powershell.exe -NoProfile -NonInteractive -Command \"docker ps --format '{{json .}}' | Select-Object -First 50 | ConvertTo-Json -Compress\"",
    ManagedReadOperation.LOGS: "powershell.exe -NoProfile -NonInteractive -Command \"Get-WinEvent -LogName System -MaxEvents 50 | Select-Object TimeCreated,Id,LevelDisplayName,Message | ConvertTo-Json -Compress\"",
})

LINUX_COMMANDS = {
    ManagedReadOperation.UPTIME: "python3 -c 'import json; print(json.dumps({\"uptime_seconds\": int(float(open(\"/proc/uptime\").read().split()[0]))}))'",
    ManagedReadOperation.MEMORY: "python3 -c 'import json; d={k:int(v.split()[0])*1024 for k,v in (line.split(\":\",1) for line in open(\"/proc/meminfo\"))}; print(json.dumps({\"total_bytes\":d[\"MemTotal\"],\"available_bytes\":d[\"MemAvailable\"]}))'",
    ManagedReadOperation.CPU: "python3 -c 'import json,os; print(json.dumps({\"load1\": os.getloadavg()[0]}))'",
    ManagedReadOperation.DISK: "df -B1 -P --output=source,size,used,avail,pcent,target | head -n 51",
    ManagedReadOperation.TEMPERATURE: "sensors -j 2>/dev/null || printf '{}'",
    ManagedReadOperation.SERVICES: "systemctl --no-pager --no-legend --type=service --state=running | head -n 50",
    ManagedReadOperation.PROCESSES: "ps -eo pid,comm,%cpu,%mem --sort=-%cpu | head -n 21",
    ManagedReadOperation.NETWORK: "ip -j address show",
    ManagedReadOperation.CONTAINERS: "docker ps --format '{{json .}}' | head -n 50",
    ManagedReadOperation.LOGS: "journalctl -n 50 --no-pager -o json",
}


def _target_from_host(host: ManagedHost) -> SshTarget:
    return SshTarget(
        user=host.user,
        host=host.host,
        identity_file=host.identity_file,
        known_hosts_file=host.known_hosts_file,
        connect_timeout_seconds=host.connect_timeout_seconds,
        max_output_bytes=host.max_output_bytes,
    )


def _degraded(host_id: str, operation: ManagedReadOperation, result: SshResult) -> dict[str, Any]:
    detail = (result.stderr or result.stdout).strip()
    return {
        "status": "degraded",
        "host": host_id,
        "operation": operation.value,
        "error": result.error or "ssh-failed",
        "detail": detail[:256],
    }


class ManagedReadService:
    def __init__(self, inventory: ManagedInventory, transport: SshTransport):
        self._inventory = inventory
        self._transport = transport

    def read(self, host_id: str, operation: ManagedReadOperation) -> dict[str, Any]:
        host = self._inventory.require_managed(host_id)
        if operation.value not in host.allowed_reads:
            raise PermissionError(f"read operation not allowed: {operation.value}")

        commands = WINDOWS_COMMANDS if host.platform.lower() == "windows" else LINUX_COMMANDS
        command = commands[operation]
        result = self._transport.run(_target_from_host(host), command)
        if result.returncode != 0:
            return _degraded(host_id, operation, result)
        return self._normalize(host_id, operation, result.stdout)

    def _normalize(self, host_id: str, operation: ManagedReadOperation, stdout: str) -> dict[str, Any]:
        base = {"status": "healthy", "host": host_id, "operation": operation.value}
        if operation is ManagedReadOperation.UPTIME:
            payload = json.loads(stdout)
            base["uptime_seconds"] = int(payload["uptime_seconds"])
            return base
        if operation is ManagedReadOperation.MEMORY:
            payload = json.loads(stdout)
            base["memory"] = {
                "total_bytes": int(payload["total_bytes"]),
                "available_bytes": int(payload["available_bytes"]),
            }
            return base
        try:
            base["data"] = json.loads(stdout)
        except json.JSONDecodeError:
            base["data"] = stdout.strip()
        return base
