#!/usr/bin/env python3
"""Allowlisted Pentium control-plane action registry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class UnknownActionError(ValueError):
    """Raised when a caller requests an action outside the registry."""


class Agent:
    def __init__(self, *, x99_status_handler: Callable[[], dict[str, Any]]):
        self._actions: dict[str, Callable[[], dict[str, Any]]] = {
            "x99.status": x99_status_handler,
        }

    def available_actions(self) -> tuple[str, ...]:
        return tuple(sorted(self._actions))

    def execute(self, action: str) -> dict[str, Any]:
        try:
            handler = self._actions[action]
        except KeyError as exc:
            raise UnknownActionError(f"unknown action: {action}") from exc
        return handler()
