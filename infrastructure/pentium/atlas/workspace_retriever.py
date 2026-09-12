from __future__ import annotations

import json

from .workspace_index import WorkspaceIndex


class WorkspaceRetriever:
    def __init__(self, index: WorkspaceIndex, *, cache=None, policy_version: str = "workspace-retrieval-v1"):
        self._index = index
        self._cache = cache
        self._policy_version = str(policy_version)

    def retrieve(self, query: str, *, max_items: int = 6, max_bytes: int = 2048) -> tuple[dict, ...]:
        if max_items <= 0 or max_bytes <= 0:
            raise ValueError("retrieval_limits_invalid")
        content_hash = self._index.fingerprint()
        cache_intent = f"items={int(max_items)};bytes={int(max_bytes)}"
        if self._cache is not None:
            cached = self._cache.get(content_hash=content_hash, query=query, intent=cache_intent, policy_version=self._policy_version)
            if cached is not None:
                return tuple(dict(item) for item in cached)

        selected: list[dict] = []
        for item in self._index.search(query, limit=max_items * 4):
            reduced = {
                "path": item["path"], "title": item["title"],
                "digest": item["digest"][:256], "sha256": item["sha256"],
                "level": "metadata",
            }
            trial = selected + [reduced]
            payload = json.dumps(trial, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            if len(payload) > max_bytes:
                continue
            selected.append(reduced)
            if len(selected) >= max_items:
                break
        result = tuple(selected)
        if self._cache is not None:
            self._cache.put(
                content_hash=content_hash,
                query=query,
                intent=cache_intent,
                policy_version=self._policy_version,
                value=list(result),
            )
        return result
