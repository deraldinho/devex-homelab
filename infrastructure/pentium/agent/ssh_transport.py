#!/usr/bin/env python3
"""Bounded SSH transport for Pentium control-plane actions."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class SshTarget:
    user: str
    host: str
    identity_file: Path
    connect_timeout_seconds: int = 5


@dataclass(frozen=True)
class SshResult:
    returncode: int
    stdout: str
    stderr: str
    error: str | None = None


Runner = Callable[..., subprocess.CompletedProcess[str]]
class SshTransport:
    def __init__(self, *, runner: Runner = subprocess.run):
        self._runner = runner

    def run(self, target: SshTarget, remote_command: str) -> SshResult:
        argv = [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "IdentitiesOnly=yes",
            "-o", "StrictHostKeyChecking=yes",
            "-o", f"ConnectTimeout={target.connect_timeout_seconds}",
            "-i", str(target.identity_file),
            f"{target.user}@{target.host}",
            remote_command,
        ]
        timeout = target.connect_timeout_seconds + 2
        try:
            completed = self._runner(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            return SshResult(124, "", "", "timeout")
        return SshResult(
            completed.returncode,
            completed.stdout,
            completed.stderr,
            None if completed.returncode == 0 else "ssh-failed",
        )
