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

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version de memoria deve ser 1")
        if self.max_records <= 0 or self.max_bytes <= 0:
            raise ValueError("bounds de memoria devem ser > 0")
        if not 0 < self.cleanup_ratio < self.consolidate_ratio < self.evict_ratio < 1:
            raise ValueError("thresholds de memoria invalidos")
        if self.retriever_max_items <= 0 or self.retriever_max_bytes <= 0:
            raise ValueError("bounds do retriever devem ser > 0")

def load_memory_config(path: str | Path) -> MemoryConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return MemoryConfig(
        schema_version=payload["schema_version"],
        max_records=payload["storage"]["max_records"],
        max_bytes=payload["storage"]["max_bytes"],
        cleanup_ratio=payload["pressure"]["cleanup_ratio"],
        consolidate_ratio=payload["pressure"]["consolidate_ratio"],
        evict_ratio=payload["pressure"]["evict_ratio"],
        retriever_max_items=payload["retriever"]["max_items"],
        retriever_max_bytes=payload["retriever"]["max_bytes"],
    )
