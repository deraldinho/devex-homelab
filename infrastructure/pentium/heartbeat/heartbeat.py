#!/usr/bin/env python3
"""Observed-state heartbeat for the Pentium control plane."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


CommandRunner = Callable[[list[str], float], CommandResult]


def run_command(command: list[str], timeout: float) -> CommandResult:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def check_unit(
    unit: str,
    *,
    user: bool,
    command_runner: CommandRunner = run_command,
) -> dict[str, Any]:
    command = ["systemctl"]
    if user:
        command.append("--user")
    command.extend(["is-active", unit])
    result = command_runner(command, 5.0)
    active = result.returncode == 0 and result.stdout.strip() == "active"
    detail = result.stdout.strip() or result.stderr.strip() or f"exit={result.returncode}"
    return {"ok": active, "required": True, "detail": detail}


def check_os(
    expected_hostname: str,
    *,
    hostname: str | None = None,
    platform_name: str | None = None,
) -> dict[str, Any]:
    observed_hostname = hostname or platform.node()
    observed_platform = platform_name or sys.platform
    ok = observed_hostname == expected_hostname and observed_platform.startswith("linux")
    return {
        "ok": ok,
        "required": True,
        "detail": f"{observed_platform}/{observed_hostname}",
    }


def check_database(path: Path) -> dict[str, Any]:
    path = path.expanduser()
    if not path.is_file():
        return {"ok": False, "required": True, "detail": "database=missing"}
    try:
        uri = f"file:{path.resolve()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=2.0) as connection:
            row = connection.execute("PRAGMA quick_check").fetchone()
    except sqlite3.Error as exc:
        return {"ok": False, "required": True, "detail": f"sqlite={exc}"}
    value = row[0] if row else "no-result"
    return {
        "ok": value == "ok",
        "required": True,
        "detail": f"quick_check={value}",
    }


def check_resources(
    *,
    disk_free_percent: float,
    memory_available_mb: int,
    min_disk_free_percent: float,
    min_memory_available_mb: int,
) -> dict[str, Any]:
    ok = (
        disk_free_percent >= min_disk_free_percent
        and memory_available_mb >= min_memory_available_mb
    )
    return {
        "ok": ok,
        "required": True,
        "detail": (
            f"disk_free={disk_free_percent:.1f}% "
            f"memory_available={memory_available_mb}MB"
        ),
    }


def read_memory_available_mb(meminfo: Path = Path("/proc/meminfo")) -> int:
    for line in meminfo.read_text(encoding="utf-8").splitlines():
        if line.startswith("MemAvailable:"):
            kib = int(line.split()[1])
            return kib // 1024
    raise RuntimeError("MemAvailable not found in /proc/meminfo")


def read_disk_free_percent(path: Path) -> float:
    usage = shutil.disk_usage(path.expanduser())
    if usage.total <= 0:
        raise RuntimeError("disk total is zero")
    return usage.free * 100.0 / usage.total


def check_core_network(
    network_health_path: Path,
    inventory_path: Path,
    *,
    command_runner: CommandRunner = run_command,
) -> dict[str, Any]:
    result = command_runner(
        [
            sys.executable,
            str(network_health_path),
            "--inventory",
            str(inventory_path),
            "--target",
            "core",
            "--json",
        ],
        8.0,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit={result.returncode}"
        return {"ok": False, "required": True, "detail": detail}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {"ok": False, "required": True, "detail": f"json={exc}"}
    healthy = payload.get("status") == "healthy"
    return {
        "ok": healthy,
        "required": True,
        "detail": f"core={payload.get('status', 'unknown')}",
    }


def summarize(
    checks: dict[str, dict[str, Any]], metrics: dict[str, Any]
) -> dict[str, Any]:
    required = [item for item in checks.values() if item.get("required", True)]
    healthy = all(bool(item.get("ok")) for item in required)
    return {
        "schema_version": 1,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "healthy" if healthy else "degraded",
        "checks": checks,
        "metrics": metrics,
    }


def write_state(path: Path, payload: dict[str, Any]) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temp_name = handle.name
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def _status(ok: bool) -> str:
    return "ok" if ok else "fail"


def render_text(summary: dict[str, Any]) -> str:
    checks = summary["checks"]
    order = [
        ("os", "OS"),
        ("tailscale", "TAILSCALE"),
        ("agent", "AGENT"),
        ("sentinel", "SENTINEL"),
        ("jobs", "JOBS"),
        ("db", "DB"),
        ("resources", "RESOURCES"),
        ("core", "CORE"),
    ]
    parts = [f"PENTIUM: {summary['status'].upper()}"]
    parts.extend(f"{label}={_status(bool(checks[key]['ok']))}" for key, label in order)
    return " | ".join(parts)


def load_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("heartbeat config schema_version must be 1")
    required = {
        "expected_hostname",
        "units",
        "database_path",
        "state_path",
        "disk_path",
        "min_disk_free_percent",
        "min_memory_available_mb",
        "network_health_path",
        "network_inventory_path",
    }
    missing = required.difference(payload)
    if missing:
        raise ValueError(f"heartbeat config missing: {sorted(missing)}")
    return payload


def _resolve(base_dir: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else base_dir / path


def collect(
    config: dict[str, Any],
    *,
    base_dir: Path,
    command_runner: CommandRunner = run_command,
) -> dict[str, Any]:
    memory_available_mb = read_memory_available_mb()
    disk_path = Path(config["disk_path"]).expanduser()
    disk_free_percent = read_disk_free_percent(disk_path)
    units = config["units"]
    checks = {
        "os": check_os(config["expected_hostname"]),
        "tailscale": check_unit(
            units["tailscale"], user=False, command_runner=command_runner
        ),
        "agent": check_unit(units["agent"], user=True, command_runner=command_runner),
        "sentinel": check_unit(
            units["sentinel"], user=True, command_runner=command_runner
        ),
        "jobs": check_unit(units["jobs"], user=True, command_runner=command_runner),
        "db": check_database(Path(config["database_path"])),
        "resources": check_resources(
            disk_free_percent=disk_free_percent,
            memory_available_mb=memory_available_mb,
            min_disk_free_percent=float(config["min_disk_free_percent"]),
            min_memory_available_mb=int(config["min_memory_available_mb"]),
        ),
        "core": check_core_network(
            _resolve(base_dir, config["network_health_path"]),
            _resolve(base_dir, config["network_inventory_path"]),
            command_runner=command_runner,
        ),
    }
    metrics = {
        "memory_available_mb": memory_available_mb,
        "disk_free_percent": round(disk_free_percent, 2),
    }
    return summarize(checks, metrics)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("config.json"),
    )
    parser.add_argument("--write-state", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        config = load_config(args.config)
        summary = collect(config, base_dir=args.config.parent)
        if args.write_state:
            write_state(Path(config["state_path"]), summary)
    except (
        OSError,
        ValueError,
        RuntimeError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"PENTIUM: ERROR | {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print(render_text(summary))
    return 0 if summary["status"] == "healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())
