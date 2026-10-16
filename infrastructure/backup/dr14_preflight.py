#!/usr/bin/env python3
"""CP-DR14 read-only Restic host readiness inventory.

Never reads the contents of environment/credential files, lists snapshots,
or modifies the host. Readiness only confirms metadata, not backup quality.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

DEFAULT_ENV = Path("/etc/homelab/backup.env")
DEFAULT_KEY = Path("/etc/homelab/secrets/restic.key")
NODE_RE = re.compile(r"[a-zA-Z0-9_-]{1,48}\Z")
UNIT_RE = re.compile(r"[a-zA-Z0-9_.@-]{1,100}\Z")


def _run(argv: list[str], timeout: int = 6) -> str:
    """Return only an enum; discard stdout/stderr to avoid leaking metadata."""
    try:
        result = subprocess.run(argv, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=timeout,
                                check=False)
        return "ok" if result.returncode == 0 else "not_ready"
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"


def _reference(path: Path) -> dict:
    """Stat only, don't follow symlinks or open/read secret-bearing files."""
    try:
        meta = path.lstat()
    except (FileNotFoundError, PermissionError, OSError):
        return {"exists": False, "regular": False, "owner_only": False}
    regular = stat.S_ISREG(meta.st_mode)
    # Owner-only permissions prevent unapproved group/world access, regardless
    # of whether the file stores a credential or only a credential reference.
    owner_only = regular and not bool(meta.st_mode & 0o077)
    return {"exists": regular, "regular": regular, "owner_only": owner_only}


def inspect_host(node: str, *,
                 backup_env: Path = DEFAULT_ENV,
                 credential_ref: Path = DEFAULT_KEY,
                 backup_timer: str = "homelab-backup.timer") -> dict:
    if not NODE_RE.fullmatch(node):
        raise ValueError("invalid_node")
    if not UNIT_RE.fullmatch(backup_timer):
        raise ValueError("invalid_unit")

    binaries = {name: shutil.which(name) is not None
                for name in ("restic", "sqlite3", "python3", "tailscale")}
    env = _reference(backup_env)
    key = _reference(credential_ref)
    timer_enabled = _run(["systemctl", "is-enabled", backup_timer])
    timer_active = _run(["systemctl", "is-active", backup_timer])
    blockers = []
    for name in ("restic", "sqlite3", "python3", "tailscale"):
        if not binaries[name]:
            blockers.append(f"{name}_binary_absent")
    if not env["owner_only"]:
        blockers.append("backup_environment_missing_or_permissions")
    if not key["owner_only"]:
        blockers.append("credential_reference_missing_or_permissions")
    if timer_enabled != "ok":
        blockers.append("backup_timer_not_enabled")
    if timer_active != "ok":
        blockers.append("backup_timer_not_active")
    return {
        "schema_version": 1,
        "checkpoint": "CP-DR14",
        "node": node,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "binaries_present": binaries,
        "backup_environment": env,
        "credential_reference": key,
        "backup_timer": {"enabled": timer_enabled, "active": timer_active},
        "blockers": blockers,
        "status": "PREFLIGHT_PRESENT_NOT_CERTIFIED" if not blockers else "BLOCKED",
        "restoration_certification": "NOT_TESTED",
        "offsite_certification": "NOT_TESTED",
        "next_gate": "operator-approved authenticated snapshots and isolated restore of actual data",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", required=True)
    parser.add_argument("--backup-env", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--credential-ref", type=Path, default=DEFAULT_KEY)
    parser.add_argument("--timer", default="homelab-backup.timer")
    parser.add_argument("--output", type=Path, default=None,
                        help="Optional new output file; without this argument, no files are changed")
    args = parser.parse_args(argv)
    try:
        result = inspect_host(args.node, backup_env=args.backup_env,
                              credential_ref=args.credential_ref,
                              backup_timer=args.timer)
        encoded = json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
        if args.output is None:
            print(encoded, end="")
        else:
            with args.output.open("x", encoding="utf-8") as output:
                output.write(encoded)
        return 0 if result["status"] != "BLOCKED" else 2
    except (OSError, ValueError):
        print('{"status":"ERROR","reason":"invalid input or inaccessible output"}',
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
