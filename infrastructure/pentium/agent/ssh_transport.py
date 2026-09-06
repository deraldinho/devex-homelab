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
    known_hosts_file: Path
    connect_timeout_seconds: int = 5
    max_output_bytes: int = 65536

    def __post_init__(self) -> None:
        if self.connect_timeout_seconds <= 0:
            raise ValueError("connect_timeout_seconds must be positive")
        if self.max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")


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
            "-o", f"UserKnownHostsFile={target.known_hosts_file}",
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
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        output_size = len(stdout.encode("utf-8")) + len(stderr.encode("utf-8"))
        if output_size > target.max_output_bytes:
            return SshResult(125, "", "", "output-limit")

        return SshResult(
            completed.returncode,
            stdout,
            stderr,
            None if completed.returncode == 0 else "ssh-failed",
        )
