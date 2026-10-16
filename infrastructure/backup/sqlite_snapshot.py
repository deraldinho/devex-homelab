"""Transactional SQLite snapshots for Restic (CP-DR12).

The Restic snapshot must EXCLUDE original .db/.sqlite/.sqlite3 source files and
INCLUDE this private stage directory. The manifest maps safe images back to
their original relative paths after restoring into a separate directory.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import sqlite3
import sys
from urllib.parse import quote

SUFFIXES = frozenset((".sqlite", ".sqlite3", ".db"))
SAFE_SUFFIX = ".sqlite-snapshot"
MAX_DATABASES = 1024


def _regular_path(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def _relative(raw: str) -> Path:
    if not isinstance(raw, str) or not raw or "\\x00" in raw or "\\" in raw:
        raise ValueError("invalid_relative_path")
    p = PurePosixPath(raw)
    if p.is_absolute() or any(x in ("", ".", "..") for x in raw.split("/")):
        raise ValueError("unsafe_relative_path")
    if PureWindowsPath(raw).drive:
        raise ValueError("unsafe_windows_path")
    return Path(*p.parts)


def _integrity_check(path: Path) -> None:
    with closing(sqlite3.connect(f"file:{quote(str(path), safe='/:')}?mode=ro", uri=True, timeout=5)) as db:
        result = db.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise ValueError("sqlite_integrity_failure")


def prepare(source: Path, stage: Path) -> dict:
    source = Path(source).resolve(strict=True)
    stage = Path(stage).resolve(strict=True)
    if not source.is_dir() or not stage.is_dir():
        raise ValueError("source_or_stage_invalid")
    if stage.is_relative_to(source) or source.is_relative_to(stage):
        raise ValueError("stage_and_source_must_be_separate")
    if (stage / "manifest.json").exists():
        raise FileExistsError("manifest_already_exists")
    records = []
    for base, dirs, files in os.walk(source, followlinks=False):
        dirs[:] = sorted(x for x in dirs if not (Path(base) / x).is_symlink())
        for name in sorted(files):
            if Path(name).suffix.lower() not in SUFFIXES:
                continue
            db_file = Path(base) / name
            if not _regular_path(db_file):
                raise ValueError("database_symlink_or_invalid")
            rel = db_file.relative_to(source).as_posix()
            rel_path = _relative(rel)
            safe_rel = Path("databases") / (str(rel_path) + SAFE_SUFFIX)
            out = stage / safe_rel
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists() or out.is_symlink():
                raise FileExistsError("staged_database_exists")
            uri = f"file:{quote(str(db_file), safe='/:')}?mode=ro"
            try:
                with closing(sqlite3.connect(uri, uri=True, timeout=5)) as original:
                    with closing(sqlite3.connect(out)) as image:
                        original.backup(image, pages=256, sleep=0.05)
                _integrity_check(out)
            except Exception:
                out.unlink(missing_ok=True)
                raise
            records.append({
                "source_relative": rel,
                "backup_relative": safe_rel.as_posix(),
            })
            if len(records) > MAX_DATABASES:
                raise ValueError("database_count_exceeded")
    manifest = {"schema_version": 1, "format": "sqlite-transactional-v1",
                "databases": records}
    tmp = stage / "manifest.json.partial"
    try:
        with tmp.open("x", encoding="utf-8") as fp:
            json.dump(manifest, fp, ensure_ascii=False, sort_keys=True)
        os.replace(tmp, stage / "manifest.json")
    finally:
        tmp.unlink(missing_ok=True)
    return manifest


def restore(stage: Path, destination: Path) -> int:
    stage = Path(stage).resolve(strict=True)
    destination = Path(destination).resolve(strict=True)
    if not stage.is_dir() or not destination.is_dir() or stage == destination:
        raise ValueError("invalid_restore_locations")
    if stage.is_relative_to(destination) or destination.is_relative_to(stage):
        raise ValueError("restore_locations_overlap")
    manifest_file = stage / "manifest.json"
    if not _regular_path(manifest_file) or manifest_file.stat().st_size > 1_000_000:
        raise ValueError("missing_or_large_manifest")
    info = json.loads(manifest_file.read_text(encoding="utf-8"))
    if (not isinstance(info, dict) or set(info) != {"schema_version", "format", "databases"}
            or info["schema_version"] != 1 or info["format"] != "sqlite-transactional-v1"
            or not isinstance(info["databases"], list) or len(info["databases"]) > MAX_DATABASES):
        raise ValueError("invalid_manifest")
    files = []
    seen = set()
    for item in info["databases"]:
        if not isinstance(item, dict) or set(item) != {"source_relative", "backup_relative"}:
            raise ValueError("invalid_manifest_record")
        rel = _relative(item["source_relative"])
        safe = _relative(item["backup_relative"])
        if safe.as_posix() != "databases/" + rel.as_posix() + SAFE_SUFFIX:
            raise ValueError("manifest_mapping_mismatch")
        if rel.as_posix() in seen:
            raise ValueError("duplicate_database")
        seen.add(rel.as_posix())
        safe_path = stage / safe
        target = destination / rel
        if target.exists() or target.is_symlink():
            raise FileExistsError("restored_database_already_exists")
        if not _regular_path(safe_path):
            raise ValueError("missing_transactional_image")
        if safe_path.resolve().is_relative_to(stage) is False:
            raise ValueError("stage_escape")
        for parent in [destination, *list(target.parents)[:-1]]:
            if parent.is_symlink():
                raise ValueError("destination_symlink")
        _integrity_check(safe_path)
        files.append((safe_path, target))
    for safe_path, target in files:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive create: never overwrite a restored file or another process.
        with target.open("xb") as dest, safe_path.open("rb") as src:
            shutil.copyfileobj(src, dest, length=1024 * 1024)
    return len(files)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "restore"))
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.mode == "prepare":
            prepare(args.source, args.target)
        else:
            restore(args.source, args.target)
        print("SQLITE_SNAPSHOT_PASS")
        return 0
    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError):
        print("SQLITE_SNAPSHOT_DENIED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
