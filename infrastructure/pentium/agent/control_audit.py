#!/usr/bin/env python3
"""Bounded audit records for managed CONTROL operations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path


@dataclass(frozen=True)
class ControlAuditRecord:
    timestamp: datetime
    phase: str
    host_id: str
    operation: str
    target: str | None
    authorized: bool
    status: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.astimezone(timezone.utc).isoformat()
        return payload


class ControlAuditJournal:
    def __init__(self, path: Path):
        self._path = Path(path)

    def append(self, record: ControlAuditRecord) -> None:
        if not isinstance(record, ControlAuditRecord):
            raise TypeError("record must be ControlAuditRecord")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        if len(line.encode("utf-8")) > 2048:
            raise ValueError("control audit record exceeds bound")
        with self._path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
