"""Non-mutating local OpenCode readiness diagnostics."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import subprocess

@dataclass(frozen=True)
class HostReadiness:
    state: str
    reason: str
    version: str | None = None

def inspect_opencode_host(binary: str, *, cpuinfo_path="/proc/cpuinfo",
                          runner=subprocess.run, timeout=8) -> HostReadiness:
    executable=Path(binary)
    if not executable.is_file():
        return HostReadiness("BLOCKED","binary_missing")
    try:
        result=runner([str(executable),"--version"],capture_output=True,
                      text=True,timeout=timeout,check=False)
    except subprocess.TimeoutExpired:
        return HostReadiness("BLOCKED","version_timeout")
    except OSError:
        return HostReadiness("BLOCKED","cannot_execute_binary")
    version=(result.stdout or "").strip()
    if result.returncode==0 and version:
        return HostReadiness("READY","version_verified",version)
    try:
        cpu=Path(cpuinfo_path).read_text(errors="replace").lower()
    except OSError:
        cpu=""
    flags=set(cpu.split())
    if "avx2" not in flags:
        return HostReadiness("BLOCKED","cpu_no_avx2_binary_failed")
    return HostReadiness("BLOCKED","binary_failed_or_empty_output")
