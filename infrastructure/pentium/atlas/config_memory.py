from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MemoryConfig:
    schema_version: int
    max_records: int
    max_bytes: int
    cleanup_ratio: float
    consolidate_ratio: float
    evict_ratio: float
    retriever_max_items: int
    retriever_max_bytes: int
    episodic_max_events: int = 32
    episodic_max_bytes: int = 8192
    episodic_max_open_segments: int = 64
    episodic_max_pending_bytes: int = 262144
    episodic_idle_timeout_s: float = 300.0

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version de memoria deve ser 1")
        if self.max_records <= 0 or self.max_bytes <= 0:
            raise ValueError("bounds de memoria devem ser > 0")
        if not 0 < self.cleanup_ratio < self.consolidate_ratio < self.evict_ratio < 1:
            raise ValueError("thresholds de memoria invalidos")
        if self.retriever_max_items <= 0 or self.retriever_max_bytes <= 0:
            raise ValueError("bounds do retriever devem ser > 0")
        episodic = (
            self.episodic_max_events,
            self.episodic_max_bytes,
            self.episodic_max_open_segments,
            self.episodic_max_pending_bytes,
        )
        if any(value <= 0 for value in episodic) or self.episodic_idle_timeout_s <= 0:
            raise ValueError("bounds episodicos devem ser > 0")
        if self.episodic_max_pending_bytes < self.episodic_max_bytes:
            raise ValueError("episodic_max_pending_bytes deve ser >= episodic_max_bytes")


def load_memory_config(path: str | Path) -> MemoryConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    episodic = payload.get("episodic", {})
    return MemoryConfig(
        schema_version=payload["schema_version"],
        max_records=payload["storage"]["max_records"],
        max_bytes=payload["storage"]["max_bytes"],
        cleanup_ratio=payload["pressure"]["cleanup_ratio"],
        consolidate_ratio=payload["pressure"]["consolidate_ratio"],
        evict_ratio=payload["pressure"]["evict_ratio"],
        retriever_max_items=payload["retriever"]["max_items"],
        retriever_max_bytes=payload["retriever"]["max_bytes"],
        episodic_max_events=int(episodic.get("max_events", 32)),
        episodic_max_bytes=int(episodic.get("max_bytes", 8192)),
        episodic_max_open_segments=int(episodic.get("max_open_segments", 64)),
        episodic_max_pending_bytes=int(episodic.get("max_pending_bytes", 262144)),
        episodic_idle_timeout_s=float(episodic.get("idle_timeout_s", 300.0)),
    )
