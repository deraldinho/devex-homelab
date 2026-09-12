from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class WorkspaceRecord:
    path: str
    created_by: str
    reason: str
    source_intent: str | None
    source_episode: str | None
    sha256: str
    size_bytes: int
    updated_at: str
    revision: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TrashRecord:
    trash_id: str
    original_path: str
    trash_path: str
    reason: str
    trashed_at: str
