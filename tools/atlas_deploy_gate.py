"""Atlas CP-DEPLOY-01: read-only release drift gate.

Compares top-level Python source hashes against a fresh, operator-collected
hash-only manifest from the *running* Pentium directory. Never copies code,
never reads credentials, never touches production or invokes SSH.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

DIGEST = re.compile(r"[a-f0-9]{64}\Z")
MODULE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\.py\Z")
ESSENTIAL = frozenset({"cognitive_daemon.py", "hermes_adapter.py",
                       "reaction_loop_cognitivo.py"})
MAX_MODULES = 500


class ReleaseGateDenied(ValueError):
    pass


def _manifest(payload: dict) -> dict[str, str]:
    if not isinstance(payload, dict) or not 0 < len(payload) <= MAX_MODULES:
        raise ReleaseGateDenied("invalid_host_manifest")
    result = {}
    for name, sha in payload.items():
        if (not isinstance(name, str) or not MODULE.fullmatch(name)
                or not isinstance(sha, str) or not DIGEST.fullmatch(sha)):
            raise ReleaseGateDenied("malformed_manifest_entry")
        result[name] = sha
    return result


def compare(source: Path, host_hashes: dict) -> dict:
    if source.is_symlink() or not source.is_dir():
        raise ReleaseGateDenied("invalid_source_directory")
    source = source.resolve(strict=True)
    remote = _manifest(host_hashes)
    local = {}
    for entry in source.iterdir():
        if entry.name.endswith(".py"):
            if entry.is_symlink() or not entry.is_file() or not MODULE.fullmatch(entry.name):
                raise ReleaseGateDenied("unsafe_source_entry")
            # Avoid a directory-traversal and accidental secrets collection.
            local[entry.name] = hashlib.sha256(entry.read_bytes()).hexdigest()
            if len(local) > MAX_MODULES:
                raise ReleaseGateDenied("module_budget_exceeded")
    if not ESSENTIAL.issubset(local) or not ESSENTIAL.issubset(remote):
        raise ReleaseGateDenied("essential_entrypoint_missing")
    changed = sorted(k for k in local.keys() & remote.keys() if local[k] != remote[k])
    added = sorted(local.keys() - remote.keys())
    host_only = sorted(remote.keys() - local.keys())
    return {
        "checkpoint": "CP-DEPLOY-01",
        "read_only": True,
        "status": "MATCHED_NO_DEPLOY" if not (changed or added or host_only) else "HOLD_DRIFT_REQUIRES_PLAN",
        "repo_modules": len(local), "host_modules": len(remote),
        "modified_existing": changed, "not_installed": added,
        "host_only_preserve": host_only,
        "deploy_allowed": False,
        "notes": "A hash match is not deployment authorization; verify tests, rollback and restore separately.",
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Atlas hash-only deployment gate")
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--host-manifest", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if args.host_manifest.is_symlink() or args.host_manifest.stat().st_size > 100_000:
            raise ReleaseGateDenied("unsafe_host_manifest")
        host = json.loads(args.host_manifest.read_text(encoding="utf-8"))
        obj = compare(args.source, host)
        print(json.dumps(obj, ensure_ascii=False, sort_keys=True))
        return 0 if obj["status"] == "MATCHED_NO_DEPLOY" else 2
    except (OSError, ValueError, UnicodeError):
        print('{"checkpoint":"CP-DEPLOY-01","status":"DENIED_INVALID_INPUT","deploy_allowed":false}')
        return 2


if __name__ == "__main__":
    sys.exit(main())
