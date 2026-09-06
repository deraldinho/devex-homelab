from __future__ import annotations

import json
from pathlib import Path

from .cognitive_cache import CognitiveCachePolicy


def load_cache_config(path: str | Path) -> CognitiveCachePolicy:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("schema_version do cache deve ser 1")
    return CognitiveCachePolicy(
        max_entries=payload["max_entries"],
        ttl_s=float(payload["ttl_s"]),
        model_id=payload["model_id"],
        policy_version=payload["policy_version"],
    )