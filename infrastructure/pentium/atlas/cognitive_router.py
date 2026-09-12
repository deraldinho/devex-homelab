from __future__ import annotations

from enum import Enum

from .token_budget_governor import TokenBudgetGovernor


class CognitiveRoute(str, Enum):
    DETERMINISTIC = "deterministic"
    CACHE = "cache"
    RETRIEVAL = "retrieval"
    LLM = "llm"
    NO_INFERENCE_REQUIRED = "no_inference_required"


class CognitiveRouter:
    _DETERMINISTIC_OPERATIONS = frozenset({
        "workspace_status", "workspace_list", "workspace_read", "workspace_search",
        "workspace_create_note", "workspace_write", "workspace_append", "workspace_move", "workspace_archive", "workspace_trash",
        "workspace_restore", "workspace_mkdir",
    })

    def __init__(self, governor: TokenBudgetGovernor):
        self._governor = governor
        self._last_fingerprint_by_kind: dict[str, str] = {}
        self._metrics = {route.value: 0 for route in CognitiveRoute}

    def metrics(self) -> dict[str, int]:
        return dict(self._metrics)

    def _count(self, route: CognitiveRoute) -> CognitiveRoute:
        self._metrics[route.value] += 1
        return route

    def route(
        self,
        *,
        kind: str,
        fingerprint: str,
        operation: str | None = None,
        cache_hit: bool = False,
        retrieval_sufficient: bool = False,
        deadline_due: bool = False,
    ) -> CognitiveRoute:
        kind = str(kind)
        if operation in self._DETERMINISTIC_OPERATIONS:
            return self._count(CognitiveRoute.DETERMINISTIC)
        if cache_hit:
            return self._count(CognitiveRoute.CACHE)
        if retrieval_sufficient:
            return self._count(CognitiveRoute.RETRIEVAL)
        previous = self._last_fingerprint_by_kind.get(kind)
        self._last_fingerprint_by_kind[kind] = fingerprint
        if kind not in {"human", "incident"} and not deadline_due and previous == fingerprint:
            return self._count(CognitiveRoute.NO_INFERENCE_REQUIRED)
        if not self._governor.allow(kind):
            return self._count(CognitiveRoute.NO_INFERENCE_REQUIRED)
        return self._count(CognitiveRoute.LLM)
