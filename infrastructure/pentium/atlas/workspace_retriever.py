from __future__ import annotations

import json

from .workspace_index import WorkspaceIndex


class WorkspaceRetriever:
    def __init__(self, index: WorkspaceIndex):
        self._index = index

    def retrieve(self, query: str, *, max_items: int = 6, max_bytes: int = 2048) -> tuple[dict, ...]:
        if max_items <= 0 or max_bytes <= 0:
            raise ValueError("retrieval_limits_invalid")
        selected: list[dict] = []
        for item in self._index.search(query, limit=max_items * 4):
            reduced = {
                "path": item["path"],
                "title": item["title"],
                "digest": item["digest"][:256],
                "sha256": item["sha256"],
                "level": "metadata",
            }
            trial = selected + [reduced]
            payload = json.dumps(trial, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            if len(payload) > max_bytes:
                continue
            selected.append(reduced)
            if len(selected) >= max_items:
                break
        return tuple(selected)
