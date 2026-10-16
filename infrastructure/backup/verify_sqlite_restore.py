"""DR-13: Validate Restic's restored SQLite images inside a disposable restore tree.

No access to the live source, no repository/network commands and no deletion.
Called only AFTER Restic restores into a private scratch directory. Supports
the CP-DR12 transactional manifest and pre-DR12 raw SQLite snapshots.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import os
from pathlib import Path
import re
import sqlite3
import sys

from sqlite_snapshot import MAX_DATABASES, restore

STAGE_NAME = re.compile(r"^\.restic-backup\.[A-Za-z0-9]{8}$")
DATABASE_SUFFIXES = frozenset((".sqlite", ".sqlite3", ".db"))
MAX_FILES = 100_000
MAX_MANIFESTS = 2
ALLOWED_STAGE_SETS = (frozenset({'sqlite'}), frozenset({'sqlite-hermes', 'sqlite-live'}))
VERIFIED_DIR = ".sqlite-verified-dr13"


class RestoreVerificationError(ValueError):
    pass


def _integrity(path: Path) -> None:
    # SQLite's mode=ro never creates missing databases.
    from urllib.parse import quote
    uri = f"file:{quote(str(path), safe='/:')}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as conn:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        if row != ("ok",):
            raise RestoreVerificationError("database_integrity_failure")


def verify(root: Path) -> dict[str, int | str]:
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise RestoreVerificationError("invalid_restore_root")
    root = root.resolve(strict=True)
    manifests: list[Path] = []
    restored_databases: list[Path] = []
    transactional_images = 0
    count = 0
    for base, dirs, files in os.walk(root, followlinks=False):
        for dirname in dirs:
            p = Path(base) / dirname
            if p.is_symlink():
                raise RestoreVerificationError("restored_symlink_forbidden")
        for filename in files:
            path = Path(base) / filename
            if path.is_symlink() or not path.is_file():
                raise RestoreVerificationError("non_regular_restore_file")
            count += 1
            if count > MAX_FILES:
                raise RestoreVerificationError("restore_file_budget_exceeded")
            if filename.endswith(".sqlite-snapshot"):
                transactional_images += 1
            if path.suffix.lower() in DATABASE_SUFFIXES:
                restored_databases.append(path)
            if filename == "manifest.json":
                if path.parent.name in {"sqlite", "sqlite-hermes", "sqlite-live"} and STAGE_NAME.fullmatch(path.parent.parent.name):
                    manifests.append(path)
                    if len(manifests) > MAX_MANIFESTS:
                        raise RestoreVerificationError("multiple_transactional_manifests")
    if transactional_images and not manifests:
        raise RestoreVerificationError("orphaned_transactional_images")
    if manifests:
        stage_names = frozenset(manifest.parent.name for manifest in manifests)
        if stage_names not in ALLOWED_STAGE_SETS:
            raise RestoreVerificationError("incomplete_or_mixed_transactional_stages")
        if len({manifest.parent.parent for manifest in manifests}) != 1:
            raise RestoreVerificationError("transactional_stages_from_different_roots")
        if restored_databases:
            # Source database inclusion along with transactional images is unsafe:
            # it could be inconsistent while the manifest image is correct.
            raise RestoreVerificationError("raw_database_present_with_transactional_manifest")
        private_dest = root / VERIFIED_DIR
        if private_dest.exists() or private_dest.is_symlink():
            raise RestoreVerificationError("verification_destination_exists")
        private_dest.mkdir(mode=0o700)
        restored_count = 0
        for manifest in sorted(manifests):
            # Legacy single-stage retains its original flat verification path.
            # The Pentium's two independent source roots must never overwrite
            # each other's paths (e.g. both can contain "runtime/state.db").
            destination = private_dest
            if stage_names != frozenset({"sqlite"}):
                destination = private_dest / manifest.parent.name
                destination.mkdir(mode=0o700)
            restored_count += restore(manifest.parent, destination)
        if restored_count < 1 or restored_count > MAX_DATABASES:
            raise RestoreVerificationError("invalid_transactional_database_count")
        if transactional_images != restored_count:
            raise RestoreVerificationError("orphaned_transactional_images")
        for base, dirs, files in os.walk(private_dest, followlinks=False):
            if any((Path(base) / name).is_symlink() for name in dirs + files):
                raise RestoreVerificationError("verification_symlink_forbidden")
            for name in files:
                if Path(name).suffix.lower() not in DATABASE_SUFFIXES:
                    raise RestoreVerificationError("unexpected_verification_file")
                _integrity(Path(base) / name)
        return {"status": "verified", "mode": "transactional",
                "sqlite_databases": restored_count}
    for db in restored_databases:
        _integrity(db)
    return {"status": "verified", "mode": "legacy",
            "sqlite_databases": len(restored_databases)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("restored_tree", type=Path)
    args = parser.parse_args(argv)
    try:
        outcome = verify(args.restored_tree)
        print(f"DR13_SQLITE_{outcome['mode'].upper()}_PASS count={outcome['sqlite_databases']}")
        return 0
    except (OSError, ValueError, sqlite3.Error):
        print("DR13_SQLITE_VERIFICATION_DENIED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
