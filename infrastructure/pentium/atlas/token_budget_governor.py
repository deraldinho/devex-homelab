from __future__ import annotations

from collections import defaultdict
from enum import Enum


class TokenBudgetMode(str, Enum):
    NORMAL = "normal"
    CONSERVATIVE = "conservative"
    RESTRICTED = "restricted"
    HUMAN_ONLY = "human_only"


class TokenBudgetGovernor:
    def __init__(self, *, window_budget: int):
        if window_budget <= 0:
            raise ValueError("window_budget_invalid")
        self.window_budget = int(window_budget)
        self._tokens_used = 0
        self._by_category = defaultdict(int)

    @property
    def pressure(self) -> float:
        return self._tokens_used / self.window_budget

    @property
    def mode(self) -> TokenBudgetMode:
        ratio = self.pressure
        if ratio >= 0.95:
            return TokenBudgetMode.HUMAN_ONLY
        if ratio >= 0.85:
            return TokenBudgetMode.RESTRICTED
        if ratio >= 0.70:
            return TokenBudgetMode.CONSERVATIVE
        return TokenBudgetMode.NORMAL

    def record(self, tokens: int, *, category: str = "other") -> None:
        if tokens < 0:
            raise ValueError("tokens_invalid")
        self._tokens_used += int(tokens)
        self._by_category[str(category)] += int(tokens)

    def allow(self, category: str) -> bool:
        category = str(category)
        if category in {"human", "incident"}:
            return True
        mode = self.mode
        if mode is TokenBudgetMode.NORMAL:
            return True
        if mode is TokenBudgetMode.CONSERVATIVE:
            return category not in {"reflection"}
        if mode is TokenBudgetMode.RESTRICTED:
            return category in {"observation"}
        return False

    def metrics(self) -> dict:
        return {
            "tokens_used": self._tokens_used,
            "window_budget": self.window_budget,
            "pressure": self.pressure,
            "mode": self.mode.value,
            "by_category": dict(self._by_category),
        }
