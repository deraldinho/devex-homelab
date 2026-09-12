from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .workspace_manifest import TrashRecord, WorkspaceRecord
from .workspace_policy import WorkspacePolicy, WorkspacePolicyError, resolve_workspace_path


class WorkspaceBrokerError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkspaceBroker:
    def __init__(self, root: Path, policy: WorkspacePolicy):
        self.root = Path(root)
        self.policy = policy
        self.root.mkdir(parents=True, exist_ok=True)
        self._system = self.root / ".system"
        self._system.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root, 0o700)
            os.chmod(self._system, 0o700)
        except OSError:
            pass
        self._manifest_path = self._system / "manifest.json"
        self._audit_path = self._system / "audit.jsonl"
        self._trash_index_path = self._system / "trash-index.json"
        if not self._manifest_path.exists():
            self._atomic_json(self._manifest_path, {"schema_version": 1, "files": {}})
        if not self._trash_index_path.exists():
            self._atomic_json(self._trash_index_path, {"schema_version": 1, "items": {}})

    def _load_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def _atomic_json(self, path: Path, payload: dict) -> None:
        self._atomic_write(path, json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")

    def _atomic_write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(path.parent, 0o700)
        except OSError:
            pass
        tmp = path.with_name(path.name + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)

    def _content_files(self) -> list[Path]:
        result = []
        for area in self.policy.allowed_areas:
            if area.startswith("."):
                continue
            base = self.root / area
            if not base.exists():
                continue
            result.extend(p for p in base.rglob("*") if p.is_file() and not p.is_symlink())
        return result

    def _usage(self, excluding: Path | None = None) -> tuple[int, int]:
        files = [p for p in self._content_files() if excluding is None or p != excluding]
        return len(files), sum(p.stat().st_size for p in files)

    def _validate_capacity(self, path: Path, content: str) -> None:
        size = len(content.encode("utf-8"))
        if size > self.policy.max_file_bytes:
            raise WorkspaceBrokerError("file_size_limit")
        exists = path.exists()
        count, total = self._usage(excluding=path if exists else None)
        if not exists and count + 1 > self.policy.max_files:
            raise WorkspaceBrokerError("file_count_limit")
        if total + size > self.policy.max_total_bytes:
            raise WorkspaceBrokerError("quota_limit")

    def _record(self, area: str, relative_path: str, content: str, *, reason: str, source_intent: str | None, source_episode: str | None) -> WorkspaceRecord:
        manifest = self._load_json(self._manifest_path)
        key = f"{area}/{Path(relative_path).as_posix()}"
        old = manifest["files"].get(key)
        record = WorkspaceRecord(
            path=key,
            created_by="atlas",
            reason=reason,
            source_intent=source_intent,
            source_episode=source_episode,
            sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            size_bytes=len(content.encode("utf-8")),
            updated_at=_utc_now(),
            revision=(int(old.get("revision", 0)) + 1) if old else 1,
        )
        manifest["files"][key] = record.to_dict()
        self._atomic_json(self._manifest_path, manifest)
        return record

    def _audit(self, operation: str, record: WorkspaceRecord) -> None:
        payload = {"operation": operation, "at": _utc_now(), **record.to_dict()}
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(self._audit_path, 0o600)
        except OSError:
            pass

    def write(self, area: str, relative_path: str, content: str, *, reason: str = "atlas", source_intent: str | None = None, source_episode: str | None = None) -> WorkspaceRecord:
        try:
            path = resolve_workspace_path(self.root, area, relative_path, self.policy)
        except WorkspacePolicyError as exc:
            raise WorkspaceBrokerError(str(exc)) from exc
        self._validate_capacity(path, content)
        self._atomic_write(path, content)
        record = self._record(area, relative_path, content, reason=reason, source_intent=source_intent, source_episode=source_episode)
        self._audit("write", record)
        return record

    def append(self, area: str, relative_path: str, content: str, *, reason: str = "atlas", source_intent: str | None = None, source_episode: str | None = None) -> WorkspaceRecord:
        path = resolve_workspace_path(self.root, area, relative_path, self.policy)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        combined = existing + content
        self._validate_capacity(path, combined)
        self._atomic_write(path, combined)
        record = self._record(area, relative_path, combined, reason=reason, source_intent=source_intent, source_episode=source_episode)
        self._audit("append", record)
        return record

    def trash(self, area: str, relative_path: str, *, reason: str = "atlas") -> TrashRecord:
        source = resolve_workspace_path(self.root, area, relative_path, self.policy)
        if not source.is_file():
            raise WorkspaceBrokerError("source_missing")
        trash_id = uuid.uuid4().hex
        trash_rel = f".trash/{trash_id}-{source.name}"
        target = self.root / trash_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        item = TrashRecord(trash_id, f"{area}/{Path(relative_path).as_posix()}", trash_rel, reason, _utc_now())
        index = self._load_json(self._trash_index_path)
        index["items"][trash_id] = item.__dict__
        self._atomic_json(self._trash_index_path, index)
        manifest = self._load_json(self._manifest_path)
        manifest["files"].pop(item.original_path, None)
        self._atomic_json(self._manifest_path, manifest)
        return item

    def restore(self, trash_id: str) -> WorkspaceRecord:
        index = self._load_json(self._trash_index_path)
        raw = index["items"].get(trash_id)
        if raw is None:
            raise WorkspaceBrokerError("trash_item_missing")
        original = Path(raw["original_path"])
        area, relative = original.parts[0], Path(*original.parts[1:]).as_posix()
        source = self.root / raw["trash_path"]
        content = source.read_text(encoding="utf-8")
        destination = resolve_workspace_path(self.root, area, relative, self.policy)
        self._validate_capacity(destination, content)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        record = self._record(area, relative, content, reason="restore", source_intent=None, source_episode=None)
        del index["items"][trash_id]
        self._atomic_json(self._trash_index_path, index)
        return record
