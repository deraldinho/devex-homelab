from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path


def _memory_available_mb(path: Path = Path("/proc/meminfo")) -> int | None:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def collect_pentium_self(*, meminfo_path: Path = Path("/proc/meminfo"), disk_path: Path = Path("/")) -> dict:
    memory_mb = _memory_available_mb(Path(meminfo_path))
    try:
        usage = shutil.disk_usage(Path(disk_path))
        disk_free_percent = round((usage.free / usage.total) * 100.0, 2) if usage.total else None
    except OSError:
        disk_free_percent = None
    memory_ok = memory_mb is not None
    disk_ok = disk_free_percent is not None
    status = "healthy" if memory_ok and disk_ok else "degraded"
    return {
        "status": status,
        "self_healthy": status == "healthy",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": {"memory": {"ok": memory_ok}, "disk": {"ok": disk_ok}},
        "metrics": {"memory_available_mb": memory_mb, "disk_free_percent": disk_free_percent},
    }
