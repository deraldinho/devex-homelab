from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class WorkspacePolicyError(ValueError):
    pass


@dataclass(frozen=True)
class WorkspacePolicy:
    allowed_areas: tuple[str, ...] = (
        "inbox", "notes", "journal", "projects", "ideas", "scratch", "artifacts", "archive", ".trash", ".system"
    )
    allowed_extensions: tuple[str, ...] = (".md", ".txt", ".json", ".jsonl", ".csv")
    max_total_bytes: int = 134217728
    max_file_bytes: int = 1048576
    max_files: int = 2048

    def __post_init__(self) -> None:
        if self.max_total_bytes <= 0 or self.max_file_bytes <= 0 or self.max_files <= 0:
            raise ValueError("workspace_limits_invalid")


def _reject_symlink_chain(root: Path, candidate: Path) -> None:
    current = root
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise WorkspacePolicyError("path_escape_forbidden") from exc
    for part in relative.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise WorkspacePolicyError("symlink_forbidden")


def resolve_workspace_path(root: Path, area: str, relative_path: str, policy: WorkspacePolicy) -> Path:
    root = Path(root).resolve(strict=False)
    if area not in policy.allowed_areas or area.startswith("."):
        raise WorkspacePolicyError("area_forbidden")
    raw = Path(relative_path)
    if raw.is_absolute():
        raise WorkspacePolicyError("absolute_path_forbidden")
    if any(part == ".." for part in raw.parts):
        raise WorkspacePolicyError("path_traversal_forbidden")
    if raw.name in {"", ".", ".."}:
        raise WorkspacePolicyError("path_invalid")
    suffix = raw.suffix.lower()
    if suffix and suffix not in policy.allowed_extensions:
        raise WorkspacePolicyError("extension_forbidden")
    area_root = root / area
    lexical_candidate = area_root / raw
    _reject_symlink_chain(root, lexical_candidate)
    candidate = lexical_candidate.resolve(strict=False)
    try:
        if os.path.commonpath((str(root), str(candidate))) != str(root):
            raise WorkspacePolicyError("path_escape_forbidden")
    except ValueError as exc:
        raise WorkspacePolicyError("path_escape_forbidden") from exc
    return lexical_candidate
